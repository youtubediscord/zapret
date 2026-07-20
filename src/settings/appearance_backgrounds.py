from __future__ import annotations

import os

from config.runtime_layout import APPLICATION_PATHS


THEME_FOLDER = str(APPLICATION_PATHS.themes_dir)


_RKN_BG_EXTENSIONS = (".jpg", ".jpeg", ".png", ".webp", ".bmp")
_RKN_BG_SCAN_FOLDERS = ("rkn_tyan", "rkn_tyan_2")
_RKN_BG_PREFERRED = (
    ("rkn_tyan/rkn_background_2.jpg", "РКН Тян — основной"),
    ("rkn_tyan/rkn_background.jpg", "РКН Тян — классический"),
    ("rkn_tyan_2/rkn_background_2.jpg", "РКН Тян 2 — основной"),
)


def normalize_theme_rel_path(value: str | None) -> str:
    raw = str(value or "").strip().replace("\\", "/")
    while raw.startswith("./"):
        raw = raw[2:]
    return raw.lstrip("/")


def theme_rel_to_abs(rel_path: str | None) -> str | None:
    rel = normalize_theme_rel_path(rel_path)
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


def build_rkn_label(rel_path: str) -> str:
    rel = normalize_theme_rel_path(rel_path)
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
        rel = normalize_theme_rel_path(rel_path)
        if not rel:
            return
        key = rel.casefold()
        if key in seen:
            return
        abs_path = theme_rel_to_abs(rel)
        if abs_path is None or not os.path.isfile(abs_path):
            return
        seen.add(key)
        options.append((rel, label or build_rkn_label(rel)))

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
    selected_rel = normalize_theme_rel_path(selected_rel_path)
    if selected_rel:
        selected_abs = theme_rel_to_abs(selected_rel)
        if selected_abs is not None and os.path.isfile(selected_abs):
            return selected_abs

    for rel, _label in _RKN_BG_PREFERRED:
        abs_path = theme_rel_to_abs(rel)
        if abs_path is not None and os.path.isfile(abs_path):
            return abs_path

    return None


_normalize_theme_rel_path = normalize_theme_rel_path
_theme_rel_to_abs = theme_rel_to_abs
_build_rkn_label = build_rkn_label


__all__ = [
    "build_rkn_label",
    "get_rkn_background_options",
    "normalize_theme_rel_path",
    "resolve_rkn_background_path",
    "theme_rel_to_abs",
]
