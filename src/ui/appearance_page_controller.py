from __future__ import annotations

from dataclasses import dataclass

from ui.text_catalog import normalize_language


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


class AppearancePageController:
    @staticmethod
    def load_display_mode() -> str:
        try:
            from config.reg import get_display_mode

            return str(get_display_mode() or "dark")
        except Exception:
            return "dark"

    @staticmethod
    def save_display_mode(mode: str) -> AppearanceDisplayModePlan:
        effective_mode = str(mode or "dark")
        try:
            from config.reg import get_display_mode, set_display_mode

            set_display_mode(mode)
            effective_mode = str(get_display_mode() or effective_mode)
        except Exception:
            pass
        return AppearanceDisplayModePlan(
            requested_mode=str(mode or "dark"),
            effective_mode=effective_mode,
        )

    @staticmethod
    def load_ui_language() -> AppearanceUiLanguagePlan:
        try:
            from config.reg import get_ui_language

            lang = normalize_language(get_ui_language())
        except Exception:
            lang = "ru"
        return AppearanceUiLanguagePlan(language=lang)

    @staticmethod
    def save_ui_language(language: str) -> AppearanceUiLanguagePlan:
        lang = normalize_language(language)
        try:
            from config.reg import set_ui_language

            set_ui_language(lang)
        except Exception:
            pass
        return AppearanceUiLanguagePlan(language=lang)

    @staticmethod
    def load_background_preset() -> AppearanceBackgroundPresetPlan:
        try:
            from config.reg import get_background_preset

            preset = str(get_background_preset() or "standard")
        except Exception:
            preset = "standard"
        return AppearanceBackgroundPresetPlan(preset=preset)

    @staticmethod
    def save_background_preset(preset: str) -> AppearanceBackgroundPresetPlan:
        normalized = str(preset or "standard")
        try:
            from config.reg import set_background_preset

            set_background_preset(normalized)
        except Exception:
            pass
        return AppearanceBackgroundPresetPlan(preset=normalized)

    @staticmethod
    def load_mica_enabled() -> AppearanceMicaPlan:
        try:
            from config.reg import get_mica_enabled

            enabled = bool(get_mica_enabled())
        except Exception:
            enabled = True
        return AppearanceMicaPlan(enabled=enabled)

    @staticmethod
    def save_mica_enabled(enabled: bool) -> AppearanceMicaPlan:
        try:
            from config.reg import set_mica_enabled

            set_mica_enabled(bool(enabled))
        except Exception:
            pass
        return AppearanceMicaPlan(enabled=bool(enabled))

    @staticmethod
    def load_window_opacity() -> AppearanceOpacityPlan:
        try:
            from config.reg import get_window_opacity

            value = int(get_window_opacity())
        except Exception:
            value = 100
        return AppearanceOpacityPlan(value=value)

    @staticmethod
    def save_window_opacity(value: int) -> AppearanceOpacityPlan:
        normalized = int(value)
        try:
            from config.reg import set_window_opacity

            set_window_opacity(normalized)
        except Exception:
            pass
        return AppearanceOpacityPlan(value=normalized)

    @staticmethod
    def load_animations_enabled() -> AppearanceTogglePlan:
        try:
            from config.reg import get_animations_enabled

            enabled = bool(get_animations_enabled())
        except Exception:
            enabled = False
        return AppearanceTogglePlan(enabled=enabled)

    @staticmethod
    def save_animations_enabled(enabled: bool) -> AppearanceTogglePlan:
        try:
            from config.reg import set_animations_enabled

            set_animations_enabled(bool(enabled))
        except Exception:
            pass
        return AppearanceTogglePlan(enabled=bool(enabled))

    @staticmethod
    def load_smooth_scroll_enabled() -> AppearanceTogglePlan:
        try:
            from config.reg import get_smooth_scroll_enabled

            enabled = bool(get_smooth_scroll_enabled())
        except Exception:
            enabled = False
        return AppearanceTogglePlan(enabled=enabled)

    @staticmethod
    def save_smooth_scroll_enabled(enabled: bool) -> AppearanceTogglePlan:
        try:
            from config.reg import set_smooth_scroll_enabled

            set_smooth_scroll_enabled(bool(enabled))
        except Exception:
            pass
        return AppearanceTogglePlan(enabled=bool(enabled))

    @staticmethod
    def load_editor_smooth_scroll_enabled() -> AppearanceTogglePlan:
        try:
            from config.reg import get_editor_smooth_scroll_enabled

            enabled = bool(get_editor_smooth_scroll_enabled())
        except Exception:
            enabled = False
        return AppearanceTogglePlan(enabled=enabled)

    @staticmethod
    def save_editor_smooth_scroll_enabled(enabled: bool) -> AppearanceTogglePlan:
        try:
            from config.reg import set_editor_smooth_scroll_enabled

            set_editor_smooth_scroll_enabled(bool(enabled))
        except Exception:
            pass
        return AppearanceTogglePlan(enabled=bool(enabled))

    @staticmethod
    def load_accent_color() -> AppearanceAccentColorPlan:
        try:
            from config.reg import get_accent_color

            hex_color = get_accent_color()
        except Exception:
            hex_color = None
        return AppearanceAccentColorPlan(hex_color=hex_color)

    @staticmethod
    def save_accent_color(hex_color: str) -> AppearanceAccentColorPlan:
        normalized = str(hex_color or "").strip()
        try:
            from config.reg import set_accent_color

            if normalized:
                set_accent_color(normalized)
        except Exception:
            pass
        return AppearanceAccentColorPlan(hex_color=normalized or None)

    @staticmethod
    def load_tinted_settings() -> AppearanceTintedSettingsPlan:
        try:
            from config.reg import (
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

    @staticmethod
    def save_follow_windows_accent(enabled: bool) -> AppearanceTogglePlan:
        try:
            from config.reg import set_follow_windows_accent

            set_follow_windows_accent(bool(enabled))
        except Exception:
            pass
        return AppearanceTogglePlan(enabled=bool(enabled))

    @staticmethod
    def save_tinted_background(enabled: bool) -> AppearanceTogglePlan:
        try:
            from config.reg import set_tinted_background

            set_tinted_background(bool(enabled))
        except Exception:
            pass
        return AppearanceTogglePlan(enabled=bool(enabled))

    @staticmethod
    def save_tinted_background_intensity(value: int) -> AppearanceOpacityPlan:
        normalized = int(value)
        try:
            from config.reg import set_tinted_background_intensity

            set_tinted_background_intensity(normalized)
        except Exception:
            pass
        return AppearanceOpacityPlan(value=normalized)

    @staticmethod
    def load_windows_system_accent() -> AppearanceAccentColorPlan:
        try:
            from config.reg import get_windows_system_accent

            hex_color = get_windows_system_accent()
        except Exception:
            hex_color = None
        return AppearanceAccentColorPlan(hex_color=hex_color)

    @staticmethod
    def load_rkn_background() -> AppearanceRknBackgroundPlan:
        try:
            from config.reg import get_rkn_background

            value = get_rkn_background()
        except Exception:
            value = None
        return AppearanceRknBackgroundPlan(value=value)

    @staticmethod
    def save_rkn_background(value: str | None) -> AppearanceRknBackgroundPlan:
        normalized = str(value).strip().replace("\\", "/") if value is not None else None
        try:
            from config.reg import set_rkn_background

            set_rkn_background(normalized)
        except Exception:
            pass
        return AppearanceRknBackgroundPlan(value=normalized or None)

    @staticmethod
    def load_premium_effects() -> AppearancePremiumEffectsPlan:
        try:
            from config.reg import get_garland_enabled, get_snowflakes_enabled

            garland = bool(get_garland_enabled())
            snowflakes = bool(get_snowflakes_enabled())
        except Exception:
            garland = False
            snowflakes = False
        return AppearancePremiumEffectsPlan(
            garland_enabled=garland,
            snowflakes_enabled=snowflakes,
        )

    @staticmethod
    def save_garland_enabled(enabled: bool) -> AppearanceTogglePlan:
        try:
            from config.reg import set_garland_enabled

            set_garland_enabled(bool(enabled))
        except Exception:
            pass
        return AppearanceTogglePlan(enabled=bool(enabled))

    @staticmethod
    def save_snowflakes_enabled(enabled: bool) -> AppearanceTogglePlan:
        try:
            from config.reg import set_snowflakes_enabled

            set_snowflakes_enabled(bool(enabled))
        except Exception:
            pass
        return AppearanceTogglePlan(enabled=bool(enabled))

    @staticmethod
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
