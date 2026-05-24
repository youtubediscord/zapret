from __future__ import annotations

import re
from typing import Optional

from PyQt6.QtGui import QColor

from app.text_catalog import tr as tr_catalog
from ui.theme import get_theme_tokens, get_themed_qta_icon
from qfluentwidgets import Action, FluentIcon


_icon_cache: dict[str, object] = {}
_DEFAULT_PRESET_ICON_COLOR = "#5caee8"
_HEX_COLOR_RGB_RE = re.compile(r"^#(?:[0-9a-fA-F]{6})$")
_HEX_COLOR_RGBA_RE = re.compile(r"^#(?:[0-9a-fA-F]{8})$")
_CSS_RGBA_COLOR_RE = re.compile(
    r"^\s*rgba?\(\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*,\s*([0-9]{1,3})\s*(?:,\s*([0-9]*\.?[0-9]+)\s*)?\)\s*$",
    re.IGNORECASE,
)
PRESET_DROP_MARKER_PROPERTY = "presetDropMarker"


def preset_drop_marker_for_target(row: int, destination_kind: str) -> dict[str, object]:
    kind = str(destination_kind or "").strip()
    try:
        row_index = int(row)
    except Exception:
        row_index = -1

    if row_index < 0:
        return {"row": -1, "mode": ""}
    if kind == "folder":
        return {"row": row_index, "mode": "folder"}
    if kind == "preset":
        return {"row": row_index, "mode": "before"}
    return {"row": -1, "mode": ""}


def tr_text(key: str, language: str, default: str, **kwargs) -> str:
    text = tr_catalog(key, language=language, default=default)
    if kwargs:
        try:
            return text.format(**kwargs)
        except Exception:
            return text
    return text


def fluent_icon(name: str):
    return getattr(FluentIcon, name, None)


def make_menu_action(text: str, *, icon=None, parent=None):
    if icon is not None:
        try:
            return Action(icon, text, parent)
        except TypeError:
            pass
    try:
        action = Action(text, parent)
    except TypeError:
        action = Action(text)
    try:
        if icon is not None:
            action.setIcon(icon)
    except Exception:
        pass
    return action


def normalize_preset_icon_color(value: Optional[str]) -> str:
    raw = str(value or "").strip()
    if _HEX_COLOR_RGB_RE.fullmatch(raw):
        return raw.lower()
    if _HEX_COLOR_RGBA_RE.fullmatch(raw):
        lowered = raw.lower()
        return f"#{lowered[1:7]}"
    try:
        return get_theme_tokens().accent_hex
    except Exception:
        return _DEFAULT_PRESET_ICON_COLOR


def cached_icon(name: str, color: str):
    key = f"{name}|{color}"
    icon = _icon_cache.get(key)
    if icon is None:
        icon = get_themed_qta_icon(name, color=color)
        _icon_cache[key] = icon
    return icon


def relative_luminance(color: QColor) -> float:
    def channel_luma(channel: int) -> float:
        value = max(0.0, min(1.0, float(channel) / 255.0))
        if value <= 0.03928:
            return value / 12.92
        return ((value + 0.055) / 1.055) ** 2.4

    return (
        0.2126 * channel_luma(color.red())
        + 0.7152 * channel_luma(color.green())
        + 0.0722 * channel_luma(color.blue())
    )


def contrast_ratio(foreground: QColor, background: QColor) -> float:
    fg = QColor(foreground)
    bg = QColor(background)
    fg.setAlpha(255)
    bg.setAlpha(255)
    l1 = relative_luminance(fg)
    l2 = relative_luminance(bg)
    lighter = max(l1, l2)
    darker = min(l1, l2)
    return (lighter + 0.05) / (darker + 0.05)


def pick_contrast_color(
    preferred_color: str,
    background_color: QColor,
    fallback_colors: list[str],
    *,
    minimum_ratio: float = 2.4,
) -> str:
    bg = QColor(background_color)
    if not bg.isValid():
        bg = QColor("#000000")
    bg.setAlpha(255)

    candidates: list[str] = []
    for raw in [preferred_color, *fallback_colors]:
        value = str(raw or "").strip()
        if value and value not in candidates:
            candidates.append(value)

    best_color = None
    best_ratio = -1.0
    for candidate in candidates:
        color = QColor(candidate)
        if not color.isValid():
            continue
        color.setAlpha(255)
        ratio = contrast_ratio(color, bg)
        if ratio >= minimum_ratio:
            return color.name(QColor.NameFormat.HexRgb)
        if ratio > best_ratio:
            best_ratio = ratio
            best_color = color

    if best_color is not None:
        return best_color.name(QColor.NameFormat.HexRgb)
    return "#f5f5f5" if relative_luminance(bg) < 0.45 else "#111111"


def to_qcolor(value, fallback_hex: str = "#000000") -> QColor:
    if isinstance(value, QColor):
        color = QColor(value)
        if color.isValid():
            return color

    text = str(value or "").strip()
    if text:
        match = _CSS_RGBA_COLOR_RE.fullmatch(text)
        if match:
            try:
                r = max(0, min(255, int(match.group(1))))
                g = max(0, min(255, int(match.group(2))))
                b = max(0, min(255, int(match.group(3))))
                alpha_raw = match.group(4)

                if alpha_raw is None:
                    a = 255
                else:
                    alpha_float = float(alpha_raw)
                    if alpha_float <= 1.0:
                        a = int(round(max(0.0, min(1.0, alpha_float)) * 255.0))
                    else:
                        a = int(round(max(0.0, min(255.0, alpha_float))))

                return QColor(r, g, b, a)
            except Exception:
                pass

        color = QColor(text)
        if color.isValid():
            return color

    fallback = QColor(fallback_hex)
    if fallback.isValid():
        return fallback
    return QColor(0, 0, 0)


__all__ = [
    "QListView",
    "PRESET_DROP_MARKER_PROPERTY",
    "cached_icon",
    "fluent_icon",
    "make_menu_action",
    "normalize_preset_icon_color",
    "pick_contrast_color",
    "preset_drop_marker_for_target",
    "to_qcolor",
    "tr_text",
]
