# ui/theme.py
import os
import re
import sys
from collections import OrderedDict
from dataclasses import dataclass
from PyQt6.QtCore import QThread, QObject, pyqtSignal
from PyQt6.QtGui import QPixmap, QColor, QIcon
from config.config import THEME_FOLDER
from settings import store as settings_store

from log.log import log

from typing import Optional
import time


_THEME_SWITCH_METRICS_ACTIVE: dict[str, object] | None = None
_THEME_SWITCH_METRICS_NEXT_ID = 0
_THEME_TOKENS_CACHE: dict[tuple, "ThemeTokens"] = {}

_DEFAULT_CARD_GRADIENT_STOPS = ("#292B37", "#252A3E")
_DEFAULT_CARD_GRADIENT_STOPS_HOVER = ("#2D3040", "#2A2F45")
_DEFAULT_CARD_DISABLED_GRADIENT_STOPS = ("#1E2232", "#171B29")
_DEFAULT_DNS_SELECTED_GRADIENT_STOPS = (
    "rgba(95, 205, 254, 0.26)",
    "rgba(95, 205, 254, 0.18)",
)
_DEFAULT_DNS_SELECTED_GRADIENT_STOPS_HOVER = (
    "rgba(95, 205, 254, 0.34)",
    "rgba(95, 205, 254, 0.24)",
)
_DEFAULT_DNS_SELECTED_BORDER = "rgba(95, 205, 254, 0.50)"
_DEFAULT_DNS_SELECTED_BORDER_HOVER = "rgba(95, 205, 254, 0.64)"
_DEFAULT_SUCCESS_SURFACE_GRADIENT_STOPS_LIGHT = (
    "rgba(82, 196, 119, 0.18)",
    "rgba(46, 160, 92, 0.12)",
)
_DEFAULT_SUCCESS_SURFACE_GRADIENT_STOPS_HOVER_LIGHT = (
    "rgba(82, 196, 119, 0.24)",
    "rgba(46, 160, 92, 0.16)",
)
_DEFAULT_SUCCESS_SURFACE_GRADIENT_STOPS_DARK = (
    "rgba(98, 214, 129, 0.22)",
    "rgba(54, 148, 88, 0.16)",
)
_DEFAULT_SUCCESS_SURFACE_GRADIENT_STOPS_HOVER_DARK = (
    "rgba(108, 224, 139, 0.30)",
    "rgba(64, 158, 98, 0.22)",
)
_DEFAULT_CONTROL_GRADIENT_STOPS_LIGHT = ("rgba(255, 255, 255, 0.92)", "rgba(243, 246, 251, 0.82)")
_DEFAULT_CONTROL_GRADIENT_STOPS_DARK = ("rgba(255, 255, 255, 0.080)", "rgba(255, 255, 255, 0.040)")
_DEFAULT_LIST_GRADIENT_STOPS_LIGHT = ("rgba(255, 255, 255, 0.88)", "rgba(244, 247, 252, 0.74)")
_DEFAULT_LIST_GRADIENT_STOPS_DARK = ("rgba(255, 255, 255, 0.075)", "rgba(255, 255, 255, 0.030)")
_DEFAULT_ITEM_HOVER_BG_LIGHT = "rgba(0, 0, 0, 0.055)"
_DEFAULT_ITEM_HOVER_BG_DARK = "rgba(255, 255, 255, 0.080)"
_DEFAULT_ITEM_SELECTED_BG_LIGHT = "rgba(68, 136, 217, 0.22)"
_DEFAULT_ITEM_SELECTED_BG_DARK = "rgba(95, 205, 254, 0.25)"
_DEFAULT_NEUTRAL_CARD_BORDER_LIGHT = "rgba(0, 0, 0, 0.10)"
_DEFAULT_NEUTRAL_CARD_BORDER_HOVER_LIGHT = "rgba(0, 0, 0, 0.16)"
_DEFAULT_NEUTRAL_CARD_BORDER_DISABLED_LIGHT = "rgba(0, 0, 0, 0.06)"
_DEFAULT_NEUTRAL_LIST_BORDER_LIGHT = "rgba(0, 0, 0, 0.10)"
_DEFAULT_NEUTRAL_CARD_BORDER_DARK = "rgba(255, 255, 255, 0.12)"
_DEFAULT_NEUTRAL_CARD_BORDER_HOVER_DARK = "rgba(255, 255, 255, 0.20)"
_DEFAULT_NEUTRAL_CARD_BORDER_DISABLED_DARK = "rgba(255, 255, 255, 0.06)"
_DEFAULT_NEUTRAL_LIST_BORDER_DARK = "rgba(255, 255, 255, 0.12)"

_DEFAULT_CARD_GRADIENT_STOPS_LIGHT = ("#FFFFFF", "#EDF3FC")
_DEFAULT_CARD_GRADIENT_STOPS_HOVER_LIGHT = ("#FFFFFF", "#E6EEFA")
_DEFAULT_CARD_DISABLED_GRADIENT_STOPS_LIGHT = ("#F3F7FD", "#E6EEF9")

_QTA_PIXMAP_CACHE_MAX = 512
_QTA_PIXMAP_CACHE: OrderedDict[tuple[str, str, int], QPixmap] = OrderedDict()

_THEME_DYNAMIC_LAYER_BEGIN = "/* __THEME_DYNAMIC_LAYER_BEGIN__ */"
_THEME_DYNAMIC_LAYER_END = "/* __THEME_DYNAMIC_LAYER_END__ */"



def set_selected_theme(theme_name: str) -> bool:
    """Сохраняет выбранную тему в settings.json."""
    result = settings_store.set_selected_theme(theme_name)
    log(f"💾 Сохранение темы в settings.json: '{theme_name}' -> {result}", "DEBUG")
    return result

def _parse_rgb(rgb: str, *, default: tuple[int, int, int] = (0, 0, 0)) -> tuple[int, int, int]:
    try:
        parts = [int(x.strip()) for x in rgb.split(",")]
        if len(parts) != 3:
            return default
        r, g, b = parts
        r = max(0, min(255, r))
        g = max(0, min(255, g))
        b = max(0, min(255, b))
        return (r, g, b)
    except Exception:
        return default


def _rgb_to_hex(rgb: tuple[int, int, int]) -> str:
    r, g, b = rgb
    return f"#{r:02x}{g:02x}{b:02x}"


def _mix_rgb(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    """Linear mix between a and b. t in [0..1]."""
    t = 0.0 if t < 0.0 else (1.0 if t > 1.0 else t)
    ar, ag, ab = a
    br, bg, bb = b
    r = int(round(ar + (br - ar) * t))
    g = int(round(ag + (bg - ag) * t))
    b2 = int(round(ab + (bb - ab) * t))
    return (
        max(0, min(255, r)),
        max(0, min(255, g)),
        max(0, min(255, b2)),
    )


def _accent_foreground_color(accent_rgb: tuple[int, int, int]) -> str:
    """Returns readable text color over accent backgrounds."""
    r, g, b = accent_rgb
    yiq = (r * 299 + g * 587 + b * 114) / 1000
    if yiq >= 160:
        return "rgba(18, 18, 18, 0.90)"
    return "rgba(245, 245, 245, 0.95)"


def _normalize_theme_name(theme_name: str | None) -> str:
    """Returns 'light' for light themes, 'dark' for dark themes."""
    raw = str(theme_name or "").strip()
    if not raw or raw == "dark":
        return "dark"
    if raw == "light":
        return "light"
    # Theme names starting with 'Светлая' are light.
    if raw.startswith("Светлая"):
        return "light"
    return "dark"

def invalidate_theme_tokens_cache() -> None:
    """Clears the theme tokens cache.

    Call when accent color changes so the next get_theme_tokens() call
    recomputes tokens with the new themeColor().
    """
    global _THEME_TOKENS_CACHE
    _THEME_TOKENS_CACHE.clear()


def _get_qfluent_themecolor() -> tuple[int, int, int] | None:
    """Returns the current qfluentwidgets theme accent as (r, g, b), or None."""
    try:
        from qfluentwidgets import themeColor
        c = themeColor()
        return (c.red(), c.green(), c.blue())
    except Exception:
        return None


def connect_qfluent_accent_signal() -> None:
    """Connects qconfig.themeColorChanged → invalidate_theme_tokens_cache.

    Call once after QApplication is created (typically in main.py).
    This ensures that whenever setThemeColor() is called, the tokens cache
    is cleared so pages re-compute CSS with the new accent.
    """
    try:
        from qfluentwidgets.common.config import qconfig
        qconfig.themeColorChanged.connect(lambda _color: invalidate_theme_tokens_cache())
    except Exception:
        pass


def _compute_tint_color(opacity_pct: int) -> tuple:
    """Compute tint overlay color for given opacity percentage.

    Returns (r, g, b, overlay_alpha) where overlay_alpha ∈ [0, 200].
    0% → overlay_alpha=0 (no tint, pure blur/Mica), 100% → 200 (heavy tint).
    """
    try:
        from qfluentwidgets import isDarkTheme
        if isDarkTheme():
            r, g, b = 32, 32, 32
        else:
            r, g, b = 242, 242, 242
    except Exception:
        r, g, b = 32, 32, 32

    try:
        from settings.appearance import load_tinted_settings
        tinted_plan = load_tinted_settings()
        if tinted_plan.tinted_background:
            intensity = tinted_plan.tinted_intensity
            accent_rgb = _get_qfluent_themecolor()
            if accent_rgb is not None and intensity > 0:
                r, g, b = _mix_rgb((r, g, b), accent_rgb, intensity / 100.0)
    except Exception:
        pass

    overlay_alpha = int(max(0, min(100, opacity_pct)) / 100.0 * 200)
    return r, g, b, overlay_alpha


def apply_aero_effect(window, opacity_pct: int) -> None:
    """Apply ACCENT_ENABLE_BLURBEHIND (Aero blur) via SetWindowCompositionAttribute.

    Lighter than Acrylic — no noise/layering overhead. Desktop shows through
    blurred, with a colour tint controlled by opacity_pct.

    opacity_pct (0–100):
        100 → fully opaque tint (solid dark/light background, blur barely visible)
          0 → no tint (pure blur of desktop content)

    Uses the library's windowEffect infrastructure:
        enableBlurBehindWindow  — primes DWM per-pixel alpha (required prerequisite)
        SetWindowCompositionAttribute(ACCENT_ENABLE_BLURBEHIND=3) — enables blur
        accentPolicy / winCompAttrData — pre-allocated in WindowsWindowEffect.__init__
    """
    if window is None:
        return
    if not hasattr(window, 'windowEffect') or not hasattr(window, 'setCustomBackgroundColor'):
        return

    import sys
    if sys.platform != 'win32':
        return
    if sys.getwindowsversion().build < 15063:  # Win10 Creators Update
        return

    try:
        is_win11_plus = sys.getwindowsversion().build >= 22000

        # Compute tint color (shared helper handles theme + accent blending)
        r, g, b, overlay_alpha = _compute_tint_color(opacity_pct)

        # Fast path for Win11 + Mica active: WCA would be a no-op since
        # DWMWA_SYSTEMBACKDROP_TYPE (Mica) takes priority over WCA on Win11 22H2+.
        # Just update the Qt tint overlay without touching DWM.
        if is_win11_plus and hasattr(window, 'isMicaEffectEnabled') and window.isMicaEffectEnabled():
            if hasattr(window, 'set_tint_overlay'):
                window.set_tint_overlay(r, g, b, overlay_alpha)
            log(f"Mica tint overlay: overlay_alpha={overlay_alpha}, rgb=({r},{g},{b})", "DEBUG")
            return

        # Map slider (0–100%) to WCA gradient alpha (0–255) for non-Mica path
        alpha = max(0, min(255, int(opacity_pct / 100.0 * 255)))

        # Pack colour as ABGR DWORD — same byte order as setAcrylicEffect:
        # input RRGGBBAA → reversed bytes → (AA<<24)|(BB<<16)|(GG<<8)|RR
        gradient_color = (alpha << 24) | (b << 16) | (g << 8) | r

        we = window.windowEffect

        # Prime DWM per-pixel alpha — required before any WCA accent call.
        we.enableBlurBehindWindow(window.winId())

        # Win11: state=4 (ACCENT_ENABLE_ACRYLICBLURBEHIND) — DirectComposition acrylic.
        # Win10: state=3 is attempted but not visible (no DirectComposition).
        #        setWindowOpacity provides the visible transparency effect instead.
        we.accentPolicy.AccentState   = 4 if is_win11_plus else 3
        we.accentPolicy.AccentFlags   = 0
        we.accentPolicy.GradientColor = gradient_color
        we.accentPolicy.AnimationId   = 0

        from ctypes import pointer as cptr
        we.SetWindowCompositionAttribute(int(window.winId()), cptr(we.winCompAttrData))

        if is_win11_plus:
            # State=4: transparent Qt paint lets DWM acrylic show through.
            # DWM 22H2+ ignores GradientColor, so tint is done via Qt overlay.
            window.setCustomBackgroundColor(QColor(0, 0, 0, 0), QColor(0, 0, 0, 0))
            if hasattr(window, 'set_tint_overlay'):
                window.set_tint_overlay(r, g, b, overlay_alpha)
            log(f"Acrylic (Win11): state=4, overlay_alpha={overlay_alpha}, rgb=({r},{g},{b})", "DEBUG")
        else:
            # Win10: solid background + window-level opacity via setWindowOpacity.
            # Map: 100% → 1.0 (opaque), 0% → 0.3 (mostly transparent, still usable).
            solid = QColor(r, g, b)
            window.setCustomBackgroundColor(solid, solid)
            win_opacity = 0.3 + (opacity_pct / 100.0) * 0.7
            window.setWindowOpacity(win_opacity)
            log(f"Win10 fallback: solid rgb=({r},{g},{b}), win_opacity={win_opacity:.2f}", "DEBUG")
    except Exception as e:
        log(f"❌ apply_aero_effect error: {e}", "DEBUG")


_RKN_BG_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
_RKN_BG_SCAN_FOLDERS = ("rkn_tyan", "rkn_tyan_2")
_RKN_BG_PREFERRED = (
    ("rkn_tyan/rkn_background_2.jpg", "РКН Тян — основной"),
    ("rkn_tyan/rkn_background.jpg", "РКН Тян — классический"),
    ("rkn_tyan_2/rkn_background_2.jpg", "РКН Тян 2 — основной"),
)


def _normalize_theme_rel_path(value: str | None) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    return raw.lstrip("/")


def _theme_rel_to_abs(rel_path: str | None) -> str | None:
    rel = _normalize_theme_rel_path(rel_path)
    if not rel:
        return None
    if rel.startswith("../") or "/../" in rel:
        return None

    candidate = os.path.abspath(os.path.join(THEME_FOLDER, *rel.split("/")))
    theme_root = os.path.abspath(THEME_FOLDER)
    candidate_norm = os.path.normcase(candidate)
    root_norm = os.path.normcase(theme_root)
    if candidate_norm != root_norm and not candidate_norm.startswith(root_norm + os.sep):
        return None
    return candidate


def _build_rkn_label(rel_path: str) -> str:
    rel = _normalize_theme_rel_path(rel_path)
    if not rel:
        return "РКН Тян"
    folder, _, file_name = rel.partition("/")
    title_prefix = "РКН Тян 2" if folder == "rkn_tyan_2" else "РКН Тян"
    stem = os.path.splitext(file_name or rel)[0].replace("_", " ").strip()
    if not stem:
        return title_prefix
    return f"{title_prefix}: {stem}"


def get_rkn_background_options() -> list[tuple[str, str]]:
    """Returns available RKN background options as (relative_path, label)."""
    options: list[tuple[str, str]] = []
    seen: set[str] = set()

    def _append(rel_path: str, label: str | None = None) -> None:
        rel = _normalize_theme_rel_path(rel_path)
        if not rel:
            return
        key = rel.casefold()
        if key in seen:
            return
        abs_path = _theme_rel_to_abs(rel)
        if abs_path is None or not os.path.isfile(abs_path):
            return
        seen.add(key)
        options.append((rel, label or _build_rkn_label(rel)))

    for rel_path, label in _RKN_BG_PREFERRED:
        _append(rel_path, label)

    for folder in _RKN_BG_SCAN_FOLDERS:
        folder_path = os.path.join(THEME_FOLDER, folder)
        if not os.path.isdir(folder_path):
            continue
        try:
            file_names = sorted(os.listdir(folder_path), key=lambda x: x.casefold())
        except Exception:
            continue
        for file_name in file_names:
            lower = file_name.lower()
            if not lower.endswith(_RKN_BG_EXTENSIONS):
                continue
            _append(f"{folder}/{file_name}")

    return options


def resolve_rkn_background_path(selected_rel_path: str | None = None) -> str | None:
    """Resolves selected RKN background rel-path to absolute existing file path."""
    selected_rel = _normalize_theme_rel_path(selected_rel_path)
    if selected_rel:
        selected_abs = _theme_rel_to_abs(selected_rel)
        if selected_abs is not None and os.path.isfile(selected_abs):
            return selected_abs

    for rel, _label in get_rkn_background_options():
        abs_path = _theme_rel_to_abs(rel)
        if abs_path is not None and os.path.isfile(abs_path):
            return abs_path

    return None


def apply_window_background(window, theme_name: str | None = None, preset: str | None = None) -> None:
    """Apply background color/image to FluentWindow based on preset."""
    if window is None:
        return

    # Determine preset
    if preset is None:
        try:
            from settings.appearance import load_background_preset
            preset = load_background_preset().preset
        except Exception:
            preset = "standard"

    try:
        from settings.appearance import load_mica_enabled
        mica_enabled = bool(load_mica_enabled().enabled)
    except Exception:
        mica_enabled = True

    # Mica is a Windows 11 system backdrop, not an interface animation.
    # The animation switch must not disable it.
    _is_win11_plus = sys.platform == 'win32' and sys.getwindowsversion().build >= 22000
    should_mica = _is_win11_plus and (preset == "standard") and mica_enabled
    if hasattr(window, 'setMicaEffectEnabled'):
        # Pre-zero stored background colors before disabling Mica (Win11 only).
        # setMicaEffectEnabled(False) immediately calls setBackgroundColor(solid)
        # which causes a flash frame before apply_aero_effect makes it transparent.
        if not should_mica and _is_win11_plus:
            prepare_transparent_mica_background = getattr(window, "prepare_transparent_mica_background", None)
            if callable(prepare_transparent_mica_background):
                prepare_transparent_mica_background()

        window.setMicaEffectEnabled(should_mica)

    # Handle background image (set_background_image if available)
    if hasattr(window, 'set_background_image'):
        if preset == "rkn_chan":
            try:
                from settings.appearance import load_rkn_background
                selected_rkn_bg = load_rkn_background().value
            except Exception:
                selected_rkn_bg = None

            rkn_path = resolve_rkn_background_path(selected_rkn_bg)
            if rkn_path is None:
                log(
                    f"⚠️ RKN background not found in themes folder: {THEME_FOLDER} (selected={selected_rkn_bg})",
                    "DEBUG",
                )
            window.set_background_image(rkn_path)
        else:
            window.set_background_image(None)

    if not hasattr(window, 'setCustomBackgroundColor'):
        return

    try:
        from PyQt6.QtGui import QColor as _QColor

        if preset == "amoled" or preset == "rkn_chan":
            # Solid black, remove any DWM effects
            if hasattr(window, 'windowEffect'):
                try:
                    window.windowEffect.removeBackgroundEffect(window.winId())
                except Exception:
                    pass
            bg = _QColor(0, 0, 0)
            window.setCustomBackgroundColor(bg, bg)
            # Clear tint overlay (may be set by apply_aero_effect on Win11)
            if hasattr(window, 'clear_tint_overlay'):
                window.clear_tint_overlay()
            # Reset Win10 window opacity (may have been set by apply_aero_effect)
            try:
                window.setWindowOpacity(1.0)
            except Exception:
                pass
            return

        # Standard preset, Mica ON:
        # setCustomBackgroundColor must use QColor(0,0,0,0) so Qt paints a fully
        # transparent surface, letting the DWM Mica layer show through.
        # Any opaque color here would paint over Mica and hide it completely.
        # The slider tint is applied as a Qt overlay on top of Mica.
        if should_mica:
            transparent = _QColor(0, 0, 0, 0)
            window.setCustomBackgroundColor(transparent, transparent)
            # Apply tint overlay based on current slider value (0%=pure Mica, 100%=heavy tint)
            if hasattr(window, 'set_tint_overlay'):
                try:
                    from settings.appearance import load_window_opacity
                    opacity_pct = load_window_opacity().value
                except Exception:
                    opacity_pct = 0
                r, g, b, overlay_alpha = _compute_tint_color(opacity_pct)
                window.set_tint_overlay(r, g, b, overlay_alpha)
            # Reset Win10 window opacity (may have been set by apply_aero_effect)
            try:
                window.setWindowOpacity(1.0)
            except Exception:
                pass
            return

        if preset == "standard":
            # Solid fallback for the default static UI. No DWM blur, no acrylic,
            # no transparent Qt surface.
            if hasattr(window, 'windowEffect'):
                try:
                    window.windowEffect.removeBackgroundEffect(window.winId())
                except Exception:
                    pass
            solid = _QColor(250, 250, 250) if get_theme_tokens().is_light else _QColor(32, 32, 32)
            window.setCustomBackgroundColor(solid, solid)
            if hasattr(window, 'clear_tint_overlay'):
                window.clear_tint_overlay()
            try:
                window.setWindowOpacity(1.0)
            except Exception:
                pass
            return

        # Non-standard fallback path.
        try:
            from settings.appearance import load_window_opacity
            opacity_pct = load_window_opacity().value
        except Exception:
            opacity_pct = 100

        apply_aero_effect(window, opacity_pct)
    except Exception:
        pass


def _sync_theme_mode_to_qfluent(theme_name: str, window=None) -> None:
    """Calls setTheme(DARK/LIGHT) to match dark/light mode hint.

    theme_name: 'Светлая*' or 'light' → LIGHT, 'system' → AUTO, anything else → DARK.
    window: if provided, also applies window background.
    """
    try:
        from qfluentwidgets import setTheme, Theme
        if str(theme_name) == "system":
            setTheme(Theme.AUTO)
        elif str(theme_name).startswith("Светлая") or str(theme_name) == "light":
            setTheme(Theme.LIGHT)
        else:
            setTheme(Theme.DARK)

        if window is not None:
            apply_window_background(window)
    except Exception:
        pass


def _sync_theme_accent_to_qfluent(theme_name: str) -> None:
    """Syncs qfluentwidgets themeColor from saved custom accent or default."""
    try:
        from qfluentwidgets.common.config import qconfig
        from PyQt6.QtGui import QColor as _QColor

        try:
            from settings.appearance import load_accent_color
            hex_color = load_accent_color().hex_color
            if hex_color:
                c = _QColor(hex_color)
                if c.isValid():
                    qconfig.set(qconfig.themeColor, c)
                    return
        except Exception:
            pass

        # Default accent: Windows 11 blue
        qconfig.set(qconfig.themeColor, _QColor(0, 120, 212))
    except Exception:
        pass


@dataclass(frozen=True)
class ThemeTokens:
    """Small set of QSS-ready tokens derived from theme_name.

    Keep this minimal and semantic: callers should use tokens instead of hard-coded
    rgba(255,255,255,...) that breaks light themes.
    """

    theme_name: str
    is_light: bool
    accent_rgb: tuple[int, int, int]
    accent_rgb_str: str
    accent_hex: str
    accent_hover_hex: str
    accent_pressed_hex: str
    accent_fg: str

    fg: str
    fg_muted: str
    fg_faint: str
    icon_fg: str
    icon_fg_muted: str
    icon_fg_faint: str

    divider: str
    divider_strong: str

    surface_bg: str
    surface_bg_hover: str
    surface_bg_pressed: str
    surface_bg_disabled: str

    surface_border: str
    surface_border_hover: str
    surface_border_disabled: str

    accent_soft_bg: str
    accent_soft_bg_hover: str

    scrollbar_track: str
    scrollbar_handle: str
    scrollbar_handle_hover: str

    toggle_off_bg: str
    toggle_off_bg_hover: str
    toggle_off_border: str
    toggle_off_disabled_bg: str
    toggle_off_disabled_border: str

    font_family_qss: str


def get_theme_tokens(theme_name: str | None = None) -> ThemeTokens:
    """Returns QSS tokens for theme-aware custom widgets.

    Accent is always the live qfluentwidgets themeColor().
    Dark/light is derived from isDarkTheme() (overrideable by theme_name hint).
    """
    try:
        from qfluentwidgets import isDarkTheme
        is_light = not isDarkTheme()
    except Exception:
        is_light = False

    # Backward compat: explicit theme_name starting with "Светлая" forces light palette
    if theme_name is not None:
        raw = str(theme_name).strip()
        if raw.startswith("Светлая") or raw == "light":
            is_light = True
        elif raw.startswith("Темная") or raw == "dark":
            is_light = False

    accent_rgb = _get_qfluent_themecolor() or (0, 120, 212)

    # Cache keyed on palette + accent (cleared on accent change)
    cache_key = ("light" if is_light else "dark", accent_rgb)
    cached = _THEME_TOKENS_CACHE.get(cache_key)
    if cached is not None:
        return cached

    token_theme_name = "light" if is_light else "dark"
    accent_rgb_str = f"{accent_rgb[0]}, {accent_rgb[1]}, {accent_rgb[2]}"
    accent_hex = _rgb_to_hex(accent_rgb)
    accent_hover_hex = _rgb_to_hex(_mix_rgb(accent_rgb, (255, 255, 255), 0.12))
    accent_pressed_hex = _rgb_to_hex(_mix_rgb(accent_rgb, (0, 0, 0), 0.12))
    accent_fg = _accent_foreground_color(accent_rgb)

    if is_light:
        fg = "rgba(0, 0, 0, 0.90)"
        fg_muted = "rgba(0, 0, 0, 0.65)"
        fg_faint = "rgba(0, 0, 0, 0.40)"
        icon_fg = "#6b7280"
        icon_fg_muted = "#7d8594"
        icon_fg_faint = "#9aa2af"
        divider = "rgba(0, 0, 0, 0.08)"
        divider_strong = "rgba(0, 0, 0, 0.14)"
        surface_bg = "rgba(0, 0, 0, 0.035)"
        surface_bg_hover = "rgba(0, 0, 0, 0.055)"
        surface_bg_pressed = "rgba(0, 0, 0, 0.075)"
        surface_bg_disabled = "rgba(0, 0, 0, 0.020)"
        surface_border = "rgba(0, 0, 0, 0.10)"
        surface_border_hover = "rgba(0, 0, 0, 0.16)"
        surface_border_disabled = "rgba(0, 0, 0, 0.06)"
        scrollbar_track = "rgba(0, 0, 0, 0.04)"
        scrollbar_handle = "rgba(0, 0, 0, 0.18)"
        scrollbar_handle_hover = "rgba(0, 0, 0, 0.28)"
        toggle_off_bg = "rgba(142, 148, 158, 0.42)"
        toggle_off_bg_hover = "rgba(134, 141, 151, 0.52)"
        toggle_off_border = "rgba(120, 127, 138, 0.64)"
        toggle_off_disabled_bg = "rgba(154, 160, 170, 0.26)"
        toggle_off_disabled_border = "rgba(138, 145, 156, 0.34)"
    else:
        fg = "rgba(255, 255, 255, 0.92)"
        fg_muted = "rgba(255, 255, 255, 0.65)"
        fg_faint = "rgba(255, 255, 255, 0.35)"
        icon_fg = "#f5f5f5"
        icon_fg_muted = "#d2d7df"
        icon_fg_faint = "#aeb5c1"
        divider = "rgba(255, 255, 255, 0.06)"
        divider_strong = "rgba(255, 255, 255, 0.10)"
        surface_bg = "rgba(255, 255, 255, 0.04)"
        surface_bg_hover = "rgba(255, 255, 255, 0.07)"
        surface_bg_pressed = "rgba(255, 255, 255, 0.10)"
        surface_bg_disabled = "rgba(255, 255, 255, 0.02)"
        surface_border = "rgba(255, 255, 255, 0.12)"
        surface_border_hover = "rgba(255, 255, 255, 0.20)"
        surface_border_disabled = "rgba(255, 255, 255, 0.06)"
        scrollbar_track = "rgba(255, 255, 255, 0.03)"
        scrollbar_handle = "rgba(255, 255, 255, 0.15)"
        scrollbar_handle_hover = "rgba(255, 255, 255, 0.25)"
        toggle_off_bg = "rgba(132, 140, 154, 0.58)"
        toggle_off_bg_hover = "rgba(144, 152, 166, 0.70)"
        toggle_off_border = "rgba(170, 178, 192, 0.84)"
        toggle_off_disabled_bg = "rgba(122, 130, 144, 0.34)"
        toggle_off_disabled_border = "rgba(150, 158, 172, 0.48)"

    accent_soft_bg = f"rgba({accent_rgb_str}, 0.15)"
    accent_soft_bg_hover = f"rgba({accent_rgb_str}, 0.20)"

    tokens = ThemeTokens(
        theme_name=token_theme_name,
        is_light=is_light,
        accent_rgb=accent_rgb,
        accent_rgb_str=accent_rgb_str,
        accent_hex=accent_hex,
        accent_hover_hex=accent_hover_hex,
        accent_pressed_hex=accent_pressed_hex,
        accent_fg=accent_fg,
        fg=fg,
        fg_muted=fg_muted,
        fg_faint=fg_faint,
        icon_fg=icon_fg,
        icon_fg_muted=icon_fg_muted,
        icon_fg_faint=icon_fg_faint,
        divider=divider,
        divider_strong=divider_strong,
        surface_bg=surface_bg,
        surface_bg_hover=surface_bg_hover,
        surface_bg_pressed=surface_bg_pressed,
        surface_bg_disabled=surface_bg_disabled,
        surface_border=surface_border,
        surface_border_hover=surface_border_hover,
        surface_border_disabled=surface_border_disabled,
        accent_soft_bg=accent_soft_bg,
        accent_soft_bg_hover=accent_soft_bg_hover,
        scrollbar_track=scrollbar_track,
        scrollbar_handle=scrollbar_handle,
        scrollbar_handle_hover=scrollbar_handle_hover,
        toggle_off_bg=toggle_off_bg,
        toggle_off_bg_hover=toggle_off_bg_hover,
        toggle_off_border=toggle_off_border,
        toggle_off_disabled_bg=toggle_off_disabled_bg,
        toggle_off_disabled_border=toggle_off_disabled_border,
        font_family_qss="'Segoe UI Variable', 'Segoe UI', Arial, sans-serif",
    )

    _THEME_TOKENS_CACHE[cache_key] = tokens
    return tokens


_RGBA_COLOR_RE = re.compile(
    r"^\s*rgba?\(\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*(?:,\s*([0-9]*\.?[0-9]+)\s*)?\)\s*$",
    re.IGNORECASE,
)


def _theme_tokens_for_icons(theme_name: str | None = None) -> ThemeTokens:
    return get_theme_tokens(theme_name)


def _parse_css_rgba_color(raw: str) -> QColor | None:
    text = str(raw or "").strip()
    match = _RGBA_COLOR_RE.fullmatch(text)
    if not match:
        return None

    try:
        r = max(0, min(255, int(match.group(1))))
        g = max(0, min(255, int(match.group(2))))
        b = max(0, min(255, int(match.group(3))))
        alpha_raw = match.group(4)

        if alpha_raw is None:
            a = 255
        else:
            a_float = float(alpha_raw)
            # Accept both [0..1] and [0..255] alpha notations.
            if a_float <= 1.0:
                a = int(round(max(0.0, min(1.0, a_float)) * 255.0))
            else:
                a = int(round(max(0.0, min(255.0, a_float))))

        return QColor(r, g, b, a)
    except Exception:
        return None


def _to_qcolor(value) -> QColor | None:
    if isinstance(value, QColor):
        return value if value.isValid() else None

    text = str(value or "").strip()
    if not text:
        return None

    # QColor does not parse CSS rgba(..., 0.92) reliably; handle it explicitly.
    parsed = _parse_css_rgba_color(text)
    if parsed is not None and parsed.isValid():
        return parsed

    color = QColor(text)
    if color.isValid():
        return color
    return None


def to_qcolor(value, fallback=None) -> QColor:
    """Parses theme/QSS color strings (including rgba with fractional alpha).

    Always returns a valid QColor (falls back to black if both values are invalid).
    """
    color = _to_qcolor(value)
    if color is not None and color.isValid():
        return QColor(color)

    fb = _to_qcolor(fallback)
    if fb is not None and fb.isValid():
        return QColor(fb)

    return QColor(0, 0, 0)


def _qcolor_to_qss_rgba(color: QColor) -> str:
    return f"rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()})"


def build_vertical_gradient_qss(top_color: str, bottom_color: str) -> str:
    """Builds a true vertical qlineargradient from two color stops."""
    return (
        "qlineargradient(x1:0, y1:0, x2:0, y2:1, "
        f"stop:0 {top_color}, stop:1 {bottom_color})"
    )


def _get_theme_gradient_stops_from_keys(
    theme_name: str,
    *,
    top_key: str,
    bottom_key: str,
    fallback: tuple[str, str],
    hover: bool = False,
    hover_top_key: str | None = None,
    hover_bottom_key: str | None = None,
    hover_fallback: tuple[str, str] | None = None,
) -> tuple[str, str]:
    """Returns default top/bottom gradient pair based on dark/light."""
    # Without THEMES dict, always return the appropriate defaults.
    if hover and hover_fallback is not None:
        return hover_fallback
    return fallback


def _get_theme_card_gradient_stops(theme_name: str, *, hover: bool = False) -> tuple[str, str]:
    """Returns card gradient stops based on dark/light mode."""
    is_light = _is_light_theme_name(theme_name)
    if is_light:
        fallback = _DEFAULT_CARD_GRADIENT_STOPS_LIGHT
        hover_fallback = _DEFAULT_CARD_GRADIENT_STOPS_HOVER_LIGHT
    else:
        fallback = _DEFAULT_CARD_GRADIENT_STOPS
        hover_fallback = _DEFAULT_CARD_GRADIENT_STOPS_HOVER
    return _get_theme_gradient_stops_from_keys(
        theme_name,
        top_key="card_gradient_top",
        bottom_key="card_gradient_bottom",
        fallback=fallback,
        hover=hover,
        hover_top_key="card_gradient_hover_top",
        hover_bottom_key="card_gradient_hover_bottom",
        hover_fallback=hover_fallback,
    )


def _get_theme_card_disabled_gradient_stops(theme_name: str) -> tuple[str, str]:
    """Returns disabled-card gradient stops based on dark/light mode."""
    is_light = _is_light_theme_name(theme_name)
    if is_light:
        fallback = _DEFAULT_CARD_DISABLED_GRADIENT_STOPS_LIGHT
    else:
        fallback = _DEFAULT_CARD_DISABLED_GRADIENT_STOPS
    return _get_theme_gradient_stops_from_keys(
        theme_name,
        top_key="card_gradient_disabled_top",
        bottom_key="card_gradient_disabled_bottom",
        fallback=fallback,
    )


def _get_theme_dns_selected_gradient_stops(
    theme_name: str,
    *,
    hover: bool = False,
) -> tuple[str, str]:
    """Returns DNS-selected gradient using live accent color."""
    tokens = get_theme_tokens(theme_name)
    r, g, b = tokens.accent_rgb
    if hover:
        return (f"rgba({r}, {g}, {b}, 0.34)", f"rgba({r}, {g}, {b}, 0.24)")
    return (f"rgba({r}, {g}, {b}, 0.26)", f"rgba({r}, {g}, {b}, 0.18)")


def _get_theme_dns_selected_border_color(theme_name: str, *, hover: bool = False) -> str:
    """Returns DNS-selected border color using live accent."""
    tokens = get_theme_tokens(theme_name)
    r, g, b = tokens.accent_rgb
    return f"rgba({r}, {g}, {b}, {'0.64' if hover else '0.50'})"


def _get_theme_success_gradient_stops(theme_name: str, *, hover: bool = False) -> tuple[str, str]:
    """Returns centralized success-surface gradient stops for a theme."""
    is_light = _is_light_theme_name(theme_name)
    fallback = (
        _DEFAULT_SUCCESS_SURFACE_GRADIENT_STOPS_LIGHT
        if is_light
        else _DEFAULT_SUCCESS_SURFACE_GRADIENT_STOPS_DARK
    )
    hover_fallback = (
        _DEFAULT_SUCCESS_SURFACE_GRADIENT_STOPS_HOVER_LIGHT
        if is_light
        else _DEFAULT_SUCCESS_SURFACE_GRADIENT_STOPS_HOVER_DARK
    )
    return _get_theme_gradient_stops_from_keys(
        theme_name,
        top_key="success_gradient_top",
        bottom_key="success_gradient_bottom",
        fallback=fallback,
        hover=hover,
        hover_top_key="success_gradient_hover_top",
        hover_bottom_key="success_gradient_hover_bottom",
        hover_fallback=hover_fallback,
    )


def _is_light_theme_name(theme_name: str) -> bool:
    s = str(theme_name)
    return s == "light" or s.startswith("Светлая")


def _get_theme_color_value(theme_name: str, key: str, fallback: str) -> str:
    return fallback


def _get_theme_control_gradient_stops(theme_name: str) -> tuple[str, str]:
    """Returns centralized header/control gradient stops for a theme."""
    is_light = _is_light_theme_name(theme_name)
    fallback = _DEFAULT_CONTROL_GRADIENT_STOPS_LIGHT if is_light else _DEFAULT_CONTROL_GRADIENT_STOPS_DARK
    return _get_theme_gradient_stops_from_keys(
        theme_name,
        top_key="control_gradient_top",
        bottom_key="control_gradient_bottom",
        fallback=fallback,
    )


def _get_theme_list_gradient_stops(theme_name: str) -> tuple[str, str]:
    """Returns centralized list/tree/table gradient stops for a theme."""
    is_light = _is_light_theme_name(theme_name)
    fallback = _DEFAULT_LIST_GRADIENT_STOPS_LIGHT if is_light else _DEFAULT_LIST_GRADIENT_STOPS_DARK
    return _get_theme_gradient_stops_from_keys(
        theme_name,
        top_key="list_gradient_top",
        bottom_key="list_gradient_bottom",
        fallback=fallback,
    )


def _get_theme_item_hover_bg(theme_name: str) -> str:
    """Returns centralized item hover background for a theme."""
    fallback = _DEFAULT_ITEM_HOVER_BG_LIGHT if _is_light_theme_name(theme_name) else _DEFAULT_ITEM_HOVER_BG_DARK
    return _get_theme_color_value(theme_name, "item_hover_bg", fallback)


def _get_theme_item_selected_bg(theme_name: str) -> str:
    """Returns item selected background using live accent color."""
    tokens = get_theme_tokens(theme_name)
    r, g, b = tokens.accent_rgb
    return f"rgba({r}, {g}, {b}, 0.22)"


def _get_theme_neutral_card_border_color(
    theme_name: str,
    *,
    hover: bool = False,
    disabled: bool = False,
) -> str:
    """Returns centralized neutral card border colors for a theme."""
    is_light = _is_light_theme_name(theme_name)
    if disabled:
        key = "neutral_card_disabled_border"
        fallback = _DEFAULT_NEUTRAL_CARD_BORDER_DISABLED_LIGHT if is_light else _DEFAULT_NEUTRAL_CARD_BORDER_DISABLED_DARK
    elif hover:
        key = "neutral_card_border_hover"
        fallback = _DEFAULT_NEUTRAL_CARD_BORDER_HOVER_LIGHT if is_light else _DEFAULT_NEUTRAL_CARD_BORDER_HOVER_DARK
    else:
        key = "neutral_card_border"
        fallback = _DEFAULT_NEUTRAL_CARD_BORDER_LIGHT if is_light else _DEFAULT_NEUTRAL_CARD_BORDER_DARK
    return _get_theme_color_value(theme_name, key, fallback)


def _get_theme_neutral_list_border_color(theme_name: str) -> str:
    """Returns centralized neutral list border color for a theme."""
    fallback = _DEFAULT_NEUTRAL_LIST_BORDER_LIGHT if _is_light_theme_name(theme_name) else _DEFAULT_NEUTRAL_LIST_BORDER_DARK
    return _get_theme_color_value(theme_name, "neutral_list_border", fallback)


def get_card_gradient_qss(theme_name: str | None = None, *, hover: bool = False) -> str:
    """Returns centralized card gradient used across framed surfaces."""
    theme = get_theme_tokens(theme_name).theme_name
    top, bottom = _get_theme_card_gradient_stops(theme, hover=hover)
    return build_vertical_gradient_qss(top, bottom)


def get_neutral_card_border_qss(
    theme_name: str | None = None,
    *,
    hover: bool = False,
    disabled: bool = False,
) -> str:
    """Returns centralized neutral card border color."""
    theme = get_theme_tokens(theme_name).theme_name
    return _get_theme_neutral_card_border_color(theme, hover=hover, disabled=disabled)


def get_card_disabled_gradient_qss(theme_name: str | None = None) -> str:
    """Returns centralized disabled card gradient used across framed surfaces."""
    theme = get_theme_tokens(theme_name).theme_name
    top, bottom = _get_theme_card_disabled_gradient_stops(theme)
    return build_vertical_gradient_qss(top, bottom)


def get_success_surface_gradient_qss(theme_name: str | None = None, *, hover: bool = False) -> str:
    """Returns centralized success surface gradient."""
    theme = get_theme_tokens(theme_name).theme_name
    top, bottom = _get_theme_success_gradient_stops(theme, hover=hover)
    return build_vertical_gradient_qss(top, bottom)


def get_tinted_surface_gradient_qss(
    base_color: str,
    *,
    theme_name: str | None = None,
    hover: bool = False,
) -> str:
    """Builds a theme-aware real gradient from an arbitrary base color."""
    tokens = get_theme_tokens(theme_name)
    parsed = _to_qcolor(base_color)
    if parsed is None:
        return get_card_gradient_qss(tokens.theme_name, hover=hover)

    alpha = max(0, min(255, parsed.alpha()))
    base_rgb = (parsed.red(), parsed.green(), parsed.blue())
    if tokens.is_light:
        top_mix = 0.16 if hover else 0.11
        bottom_mix = 0.10 if hover else 0.06
    else:
        top_mix = 0.12 if hover else 0.08
        bottom_mix = 0.18 if hover else 0.13

    top_rgb = _mix_rgb(base_rgb, (255, 255, 255), top_mix)
    bottom_rgb = _mix_rgb(base_rgb, (0, 0, 0), bottom_mix)
    top = _qcolor_to_qss_rgba(QColor(top_rgb[0], top_rgb[1], top_rgb[2], alpha))
    bottom = _qcolor_to_qss_rgba(QColor(bottom_rgb[0], bottom_rgb[1], bottom_rgb[2], alpha))
    return build_vertical_gradient_qss(top, bottom)


def resolve_icon_color(color=None, *, theme_name: str | None = None, muted_fallback: bool = False) -> str:
    """Converts arbitrary icon color input to a qtawesome/QColor-safe color string."""
    tokens = _theme_tokens_for_icons(theme_name)
    fallback = tokens.icon_fg_muted if muted_fallback else tokens.icon_fg

    if color is None:
        return fallback

    # Map semantic text tokens to dedicated icon palette.
    raw = str(color).strip()
    if raw == tokens.fg:
        return tokens.icon_fg
    if raw == tokens.fg_muted:
        return tokens.icon_fg_muted
    if raw == tokens.fg_faint:
        return tokens.icon_fg_faint

    parsed = _to_qcolor(color)
    if parsed is None:
        return fallback

    # Normalize near-black icon colors to theme fallback:
    # light themes -> gray, dark themes -> light icon color.
    if parsed.red() < 26 and parsed.green() < 26 and parsed.blue() < 26:
        return fallback

    return parsed.name(QColor.NameFormat.HexArgb)


def get_cached_qta_pixmap(
    icon_name: str,
    *,
    color=None,
    size: int = 16,
    theme_name: str | None = None,
    muted_fallback: bool = False,
) -> QPixmap:
    """Returns cached qtawesome pixmap for icon+color+size."""
    try:
        import qtawesome as qta
    except Exception:
        return QPixmap()

    safe_size = max(1, int(size))
    resolved_color = resolve_icon_color(color, theme_name=theme_name, muted_fallback=muted_fallback)
    key = (str(icon_name or ""), resolved_color, safe_size)

    cached = _QTA_PIXMAP_CACHE.get(key)
    if cached is not None and not cached.isNull():
        _QTA_PIXMAP_CACHE.move_to_end(key)
        return QPixmap(cached)

    try:
        pixmap = qta.icon(icon_name, color=resolved_color).pixmap(safe_size, safe_size)
    except Exception:
        return QPixmap()

    _QTA_PIXMAP_CACHE[key] = QPixmap(pixmap)
    _QTA_PIXMAP_CACHE.move_to_end(key)
    while len(_QTA_PIXMAP_CACHE) > _QTA_PIXMAP_CACHE_MAX:
        _QTA_PIXMAP_CACHE.popitem(last=False)

    return pixmap


def get_themed_qta_icon(
    icon_name: str,
    *,
    color=None,
    theme_name: str | None = None,
    muted_fallback: bool = False,
    **kwargs,
) -> QIcon:
    """Returns qtawesome icon with explicit local color normalization.

    This helper lets use-sites avoid relying on the global qta.icon monkey-patch.
    """
    try:
        import qtawesome as qta
    except Exception:
        return QIcon()

    local_kwargs = dict(kwargs)
    local_kwargs["color"] = resolve_icon_color(
        local_kwargs.get("color", color),
        theme_name=theme_name,
        muted_fallback=muted_fallback,
    )
    if "color_disabled" in local_kwargs:
        local_kwargs["color_disabled"] = resolve_icon_color(
            local_kwargs.get("color_disabled"),
            theme_name=theme_name,
            muted_fallback=True,
        )
    if "color_active" in local_kwargs:
        local_kwargs["color_active"] = resolve_icon_color(
            local_kwargs.get("color_active"),
            theme_name=theme_name,
            muted_fallback=False,
        )
    if "color_selected" in local_kwargs:
        local_kwargs["color_selected"] = resolve_icon_color(
            local_kwargs.get("color_selected"),
            theme_name=theme_name,
            muted_fallback=False,
        )
    if "color_on" in local_kwargs:
        local_kwargs["color_on"] = resolve_icon_color(
            local_kwargs.get("color_on"),
            theme_name=theme_name,
            muted_fallback=False,
        )
    if "color_off" in local_kwargs:
        local_kwargs["color_off"] = resolve_icon_color(
            local_kwargs.get("color_off"),
            theme_name=theme_name,
            muted_fallback=True,
        )

    try:
        return qta.icon(icon_name, **local_kwargs)
    except Exception:
        return QIcon()

class ThemeBuildWorker(QObject):
    """Worker for theme CSS preparation. Returns empty CSS (qfluentwidgets handles styling)."""

    finished = pyqtSignal(str, str)  # final_css, theme_name
    error = pyqtSignal(str)
    progress = pyqtSignal(str)  # status message

    def __init__(self, theme_name: str):
        super().__init__()
        self.theme_name = theme_name

    def run(self):
        try:
            self.progress.emit("Applying theme...")
            self.finished.emit("", self.theme_name)
        except Exception as e:
            self.error.emit(str(e))


class ThemeManager:
    """Класс для управления текущей темой приложения."""

    def __init__(self, app, widget):
        self.app = app
        self.widget = widget
        self._cleanup_in_progress = False

        # Потоки для асинхронной генерации CSS темы
        self._theme_build_thread: Optional[QThread] = None
        self._theme_build_worker: Optional[ThemeBuildWorker] = None
        self._theme_request_seq = 0
        self._latest_theme_request_id = 0
        self._latest_requested_theme: str | None = None
        self._active_theme_build_jobs: dict[int, tuple[QThread, ThemeBuildWorker]] = {}
        

        # список тем — теперь пустой (тема определяется isDarkTheme() системно)
        self.themes = []
        # Initialize from current qfluentwidgets state to avoid overriding startup setTheme()
        try:
            from qfluentwidgets import isDarkTheme
            self.current_theme = "Светлая синяя" if not isDarkTheme() else "Темная синяя"
        except Exception:
            self.current_theme = "Темная синяя"
        log("🎨 ThemeManager: режим из isDarkTheme(), тема не выбирается", "DEBUG")

        # Минимальный CSS теперь применяется в main.py ДО показа окна

    def cleanup(self):
        """Безопасная очистка всех ресурсов"""
        try:
            self._cleanup_in_progress = True

            # Останавливаем фоновые задачи сборки тем (если остались)
            for _, (thread, _) in list(self._active_theme_build_jobs.items()):
                try:
                    if thread.isRunning():
                        thread.quit()
                        if not thread.wait(1000):
                            log("Принудительное завершение потока сборки темы", "WARNING")
                            thread.terminate()
                            thread.wait(500)
                except RuntimeError:
                    pass
            self._cleanup_theme_build_thread()
                    
            log("ThemeManager очищен", "DEBUG")
            
        except Exception as e:
            log(f"Ошибка при очистке ThemeManager: {e}", "ERROR")

    def get_clean_theme_name(self, display_name):
        """Извлекает чистое имя темы из отображаемого названия"""
        return str(display_name or "").strip()

    def apply_theme_async(self, theme_name: str | None = None, *, persist: bool = True,
                          progress_callback=None, done_callback=None) -> None:
        """
        Асинхронно применяет тему (не блокирует UI).
        CSS генерируется в фоновом потоке, применяется в главном.

        Args:
            theme_name: Имя темы (если None, используется текущая)
            persist: Сохранять ли выбор в реестр
            progress_callback: Функция для обновления прогресса (str)
            done_callback: Функция вызываемая после завершения (bool success, str message)
        """
        if self._cleanup_in_progress:
            return
        if theme_name is None:
            theme_name = self.current_theme

        clean = self.get_clean_theme_name(theme_name)

        # Быстрый дедуп одинакового последнего запроса, если он всё ещё в работе.
        if self._latest_requested_theme == clean and self._latest_theme_request_id in self._active_theme_build_jobs:
            log(f"⏭️ Тема '{clean}' уже запрошена, игнорируем дубликат", "DEBUG")
            return

        try:
            if progress_callback:
                progress_callback("Подготовка темы...")

            self._theme_request_seq += 1
            request_id = self._theme_request_seq
            self._latest_theme_request_id = request_id
            self._latest_requested_theme = clean

            request_data = {
                'theme_name': clean,
                'persist': persist,
                'done_callback': done_callback,
                'progress_callback': progress_callback,
            }

            log(
                f"🎨 Запуск асинхронной подготовки темы: {clean} (request_id={request_id})",
                "DEBUG",
            )

            thread = QThread(self.widget)
            worker = ThemeBuildWorker(theme_name=clean)
            worker.moveToThread(thread)

            thread.started.connect(worker.run)
            worker.finished.connect(
                lambda final_css, built_theme, rid=request_id, data=request_data:
                self._on_theme_css_ready(final_css, built_theme, rid, data)
            )
            worker.error.connect(
                lambda error, rid=request_id, data=request_data:
                self._on_theme_build_error(error, rid, data)
            )
            if progress_callback:
                worker.progress.connect(
                    lambda status, rid=request_id, cb=progress_callback:
                    (rid == self._latest_theme_request_id) and cb(status)
                )

            # Важно: завершаем поток и при успехе, и при ошибке.
            worker.finished.connect(thread.quit)
            worker.error.connect(thread.quit)
            thread.finished.connect(lambda rid=request_id: self._cleanup_theme_build_thread(rid))

            self._active_theme_build_jobs[request_id] = (thread, worker)
            self._theme_build_thread = thread
            self._theme_build_worker = worker
            thread.start()

        except Exception as e:
            log(f"Ошибка запуска асинхронного применения темы: {e}", "❌ ERROR")
            if done_callback:
                done_callback(False, str(e))

    def _on_theme_css_ready(
        self,
        final_css: str,
        theme_name: str,
        request_id: int | None = None,
        request_data: Optional[dict] = None,
    ):
        """Обработчик готовности CSS (вызывается из главного потока).

        Применяет CSS только для актуального (последнего) запроса.
        """
        if self._cleanup_in_progress:
            return
        done_callback = None
        try:
            data = request_data or {}
            requested_theme = str(data.get('theme_name') or theme_name)
            persist = bool(data.get('persist', True))
            done_callback = data.get('done_callback')
            progress_callback = data.get('progress_callback')

            if request_id is not None and request_id != self._latest_theme_request_id:
                log(
                    f"⏭️ Игнорируем устаревший CSS результат (request_id={request_id}, latest={self._latest_theme_request_id})",
                    "DEBUG",
                )
                return

            if progress_callback:
                progress_callback("Применяем тему...")

            log(
                f"🎨 CSS готов ({len(final_css)} символов), применяем: {requested_theme} (request_id={request_id})",
                "DEBUG",
            )

            # Применяем готовый CSS - это ЕДИНСТВЕННАЯ синхронная операция!
            self._apply_css_only(final_css, requested_theme, persist)

            if done_callback:
                try:
                    done_callback(True, "ok")
                except Exception as cb_error:
                    log(f"Ошибка в done_callback: {cb_error}", "WARNING")

        except Exception as e:
            log(f"Ошибка применения готового CSS: {e}", "❌ ERROR")
            import traceback
            log(traceback.format_exc(), "DEBUG")

            if done_callback:
                try:
                    done_callback(False, str(e))
                except Exception as cb_error:
                    log(f"Ошибка в error callback: {cb_error}", "WARNING")

    def _on_theme_build_error(
        self,
        error: str,
        request_id: int | None = None,
        request_data: Optional[dict] = None,
    ):
        """Обработчик ошибки генерации CSS"""
        if self._cleanup_in_progress:
            return
        log(f"❌ Ошибка генерации CSS темы: {error}", "ERROR")

        if request_id is not None and request_id != self._latest_theme_request_id:
            log(
                f"⏭️ Игнорируем устаревшую ошибку темы (request_id={request_id}, latest={self._latest_theme_request_id})",
                "DEBUG",
            )
            return

        done_callback = None
        if request_data:
            done_callback = request_data.get('done_callback')
        if done_callback:
            done_callback(False, error)

    def _cleanup_theme_build_thread(self, request_id: int | None = None):
        """Очистка потока генерации CSS по request_id."""
        try:
            ids_to_cleanup = [request_id] if request_id is not None else list(self._active_theme_build_jobs.keys())
            for rid in ids_to_cleanup:
                if rid is None:
                    continue
                job = self._active_theme_build_jobs.pop(rid, None)
                if not job:
                    continue
                thread, worker = job
                try:
                    worker.deleteLater()
                except RuntimeError:
                    pass
                try:
                    thread.deleteLater()
                except RuntimeError:
                    pass

            latest_job = self._active_theme_build_jobs.get(self._latest_theme_request_id)
            if latest_job:
                self._theme_build_thread, self._theme_build_worker = latest_job
            else:
                self._theme_build_thread = None
                self._theme_build_worker = None

        except RuntimeError:
            self._theme_build_worker = None
            self._theme_build_thread = None
    
    def _apply_css_only(self, final_css: str, theme_name: str, persist: bool):
        """Sync qfluentwidgets theme state without a main-window stylesheet.

        qfluentwidgets manages all widget styling natively via setTheme(DARK/LIGHT).
        Applying an overlay CSS via main_window.setStyleSheet() would inject hardcoded
        dark-mode QLabel colors (color: rgba(255,255,255,0.87)) that survive light-mode
        switches → white text on white background.
        """
        try:
            if not self.widget or not self.app:
                return

            clean = _normalize_theme_name(theme_name)

            # Sync qfluentwidgets dark/light mode — updates all native widgets.
            _sync_theme_mode_to_qfluent(clean, window=self.widget)

            # Sync accent color and invalidate token cache.
            _sync_theme_accent_to_qfluent(clean)
            invalidate_theme_tokens_cache()

            self.current_theme = clean

            if persist:
                set_selected_theme(clean)
                log(f"💾 Тема сохранена: '{clean}'", "DEBUG")

        except Exception as e:
            log(f"Ошибка в _apply_css_only: {e}", "❌ ERROR")

    def _set_status(self, text):
        """Устанавливает текст статуса (через главное окно)"""
        if hasattr(self.widget, 'set_status'):
            self.widget.set_status(text)
