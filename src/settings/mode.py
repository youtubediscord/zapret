from __future__ import annotations

import os

ZAPRET2_MODE = "zapret2_mode"
ZAPRET1_MODE = "zapret1_mode"
ORCHESTRA_MODE = "orchestra"

DEFAULT_LAUNCH_METHOD = ZAPRET2_MODE

ALL_LAUNCH_METHODS = frozenset(
    (
        ZAPRET2_MODE,
        ZAPRET1_MODE,
        ORCHESTRA_MODE,
    )
)

PRESET_LAUNCH_METHODS = frozenset(
    (
        ZAPRET2_MODE,
        ZAPRET1_MODE,
    )
)

ENGINE_WINWS1 = "winws1"
ENGINE_WINWS2 = "winws2"
ALL_ENGINES = frozenset((ENGINE_WINWS1, ENGINE_WINWS2))

ENGINE_BY_LAUNCH_METHOD = {
    ZAPRET2_MODE: ENGINE_WINWS2,
    ZAPRET1_MODE: ENGINE_WINWS1,
}

DEFAULT_PRESET_FILE_NAME_BY_ENGINE = {
    ENGINE_WINWS1: "Default v1.txt",
    ENGINE_WINWS2: "Default v1 (game filter).txt",
}

EXE_NAME_WINWS1 = "winws.exe"
EXE_NAME_WINWS2 = "winws2.exe"
ALL_WINWS_EXE_NAMES = (EXE_NAME_WINWS1, EXE_NAME_WINWS2)
ALL_WINWS_EXE_NAME_SET = frozenset(ALL_WINWS_EXE_NAMES)
WINWS_ENGINE_FAMILY_LABEL = f"{ENGINE_WINWS1}/{ENGINE_WINWS2}"
WINWS_EXE_FAMILY_LABEL = f"{EXE_NAME_WINWS1}/{EXE_NAME_WINWS2}"

RELATIVE_EXE_PATH_WINWS1 = os.path.join("exe", EXE_NAME_WINWS1)
RELATIVE_EXE_PATH_WINWS2 = os.path.join("exe", EXE_NAME_WINWS2)

SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS1 = f"selected_source_preset_file_name_{ENGINE_WINWS1}"
SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS2 = f"selected_source_preset_file_name_{ENGINE_WINWS2}"

PRESETS_SCOPE_WINWS1 = ENGINE_WINWS1
PRESETS_SCOPE_WINWS2 = ENGINE_WINWS2
PRESETS_DIR_NAME_WINWS1 = PRESETS_SCOPE_WINWS1
PRESETS_DIR_NAME_WINWS2 = PRESETS_SCOPE_WINWS2
BUILTIN_PRESETS_DIR_NAME_WINWS1 = f"{PRESETS_DIR_NAME_WINWS1}_builtin"
BUILTIN_PRESETS_DIR_NAME_WINWS2 = f"{PRESETS_DIR_NAME_WINWS2}_builtin"

EXE_NAME_BY_LAUNCH_METHOD = {
    ZAPRET2_MODE: EXE_NAME_WINWS2,
    ZAPRET1_MODE: EXE_NAME_WINWS1,
    ORCHESTRA_MODE: EXE_NAME_WINWS2,
}


def normalize_launch_method(value: object, *, default: str = DEFAULT_LAUNCH_METHOD) -> str:
    method = str(value or "").strip().lower()
    if method in ALL_LAUNCH_METHODS:
        return method
    return default


def require_launch_method(value: object) -> str:
    method = str(value or "").strip().lower()
    if method in ALL_LAUNCH_METHODS:
        return method
    raise ValueError(f"Unsupported launch method: {value!r}")


def is_known_launch_method(value: object) -> bool:
    return str(value or "").strip().lower() in ALL_LAUNCH_METHODS


def is_preset_launch_method(value: object) -> bool:
    return str(value or "").strip().lower() in PRESET_LAUNCH_METHODS


def is_orchestra_launch_method(value: object) -> bool:
    return str(value or "").strip().lower() == ORCHESTRA_MODE


def is_zapret2_launch_method(value: object) -> bool:
    return str(value or "").strip().lower() == ZAPRET2_MODE


def is_zapret1_launch_method(value: object) -> bool:
    return str(value or "").strip().lower() == ZAPRET1_MODE


def engine_for_launch_method(value: object) -> str:
    method = require_launch_method(value)
    try:
        return ENGINE_BY_LAUNCH_METHOD[method]
    except KeyError as exc:
        raise ValueError(f"Launch method has no preset engine: {method}") from exc


def engine_for_launch_method_or_none(value: object) -> str | None:
    method = str(value or "").strip().lower()
    return ENGINE_BY_LAUNCH_METHOD.get(method)


def exe_name_for_launch_method(value: object) -> str:
    method = require_launch_method(value)
    return EXE_NAME_BY_LAUNCH_METHOD[method]


def exe_path_for_launch_method(value: object) -> str:
    from config.runtime_layout import APPLICATION_PATHS

    return str(APPLICATION_PATHS.exe_dir / exe_name_for_launch_method(value))


__all__ = [
    "ALL_ENGINES",
    "ALL_LAUNCH_METHODS",
    "ALL_WINWS_EXE_NAME_SET",
    "ALL_WINWS_EXE_NAMES",
    "BUILTIN_PRESETS_DIR_NAME_WINWS1",
    "BUILTIN_PRESETS_DIR_NAME_WINWS2",
    "DEFAULT_LAUNCH_METHOD",
    "DEFAULT_PRESET_FILE_NAME_BY_ENGINE",
    "ENGINE_BY_LAUNCH_METHOD",
    "ENGINE_WINWS1",
    "ENGINE_WINWS2",
    "EXE_NAME_BY_LAUNCH_METHOD",
    "EXE_NAME_WINWS1",
    "EXE_NAME_WINWS2",
    "ORCHESTRA_MODE",
    "PRESETS_SCOPE_WINWS1",
    "PRESETS_SCOPE_WINWS2",
    "PRESETS_DIR_NAME_WINWS1",
    "PRESETS_DIR_NAME_WINWS2",
    "PRESET_LAUNCH_METHODS",
    "RELATIVE_EXE_PATH_WINWS1",
    "RELATIVE_EXE_PATH_WINWS2",
    "SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS1",
    "SELECTED_SOURCE_PRESET_FILE_NAME_KEY_WINWS2",
    "WINWS_ENGINE_FAMILY_LABEL",
    "WINWS_EXE_FAMILY_LABEL",
    "ZAPRET1_MODE",
    "ZAPRET2_MODE",
    "engine_for_launch_method",
    "engine_for_launch_method_or_none",
    "exe_name_for_launch_method",
    "exe_path_for_launch_method",
    "is_known_launch_method",
    "is_orchestra_launch_method",
    "is_preset_launch_method",
    "is_zapret1_launch_method",
    "is_zapret2_launch_method",
    "normalize_launch_method",
    "require_launch_method",
]
