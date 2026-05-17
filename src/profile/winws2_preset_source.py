from __future__ import annotations

import re


CORE_LUA_INITS: tuple[str, ...] = (
    "lua/zapret-lib.lua",
    "lua/zapret-antidpi.lua",
    "lua/zapret-auto.lua",
    "lua/custom_funcs.lua",
    "lua/custom_diag.lua",
)

EXTENSION_LUA_INITS: dict[str, set[str]] = {
    "lua/zapret-multishake.lua": {
        "hostfakesplit_stealth",
        "hostfakesplit_chaos",
        "hostfakesplit_multi",
        "hostfakesplit_gradual",
        "hostfakesplit_decoy",
    },
    "lua/fakemultisplit.lua": {
        "fakemultisplit",
    },
    "lua/fakemultidisorder.lua": {
        "fakemultidisorder",
    },
}

_LUA_DESYNC_FUNC_RE = re.compile(r"--lua-desync=([a-z0-9_]+)", re.IGNORECASE)
_LUA_INIT_RE = re.compile(r"--lua-init=@?(.+)", re.IGNORECASE)
_STRATEGY_TAG_RE = re.compile(r":strategy=\d+", re.IGNORECASE)
_CIRCULAR_LUA_DESYNC_RE = re.compile(r"(?<!\S)--lua-desync=circular(?::\S*)?(?=\s|$)", re.IGNORECASE)


def is_winws2_circular_preset_source(source_text: str) -> bool:
    for raw in str(source_text or "").replace("\r\n", "\n").replace("\r", "\n").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if _CIRCULAR_LUA_DESYNC_RE.search(stripped):
            return True
    return False


def has_winws2_strategy_tags(source_text: str) -> bool:
    for raw in str(source_text or "").replace("\r\n", "\n").replace("\r", "\n").splitlines():
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.lower().startswith("--lua-desync=") and _STRATEGY_TAG_RE.search(stripped):
            return True
    return False


def ensure_winws2_lua_init_lines(source_text: str) -> str:
    text = str(source_text or "").replace("\r\n", "\n").replace("\r", "\n")
    lines = text.split("\n")

    existing_inits: set[str] = set()
    used_funcs: set[str] = set()
    for raw in lines:
        stripped = raw.strip()
        if not stripped or stripped.startswith("#"):
            continue
        init_match = _LUA_INIT_RE.match(stripped)
        if init_match:
            existing_inits.add(init_match.group(1).strip().replace("\\", "/").lower())
        for func_match in _LUA_DESYNC_FUNC_RE.finditer(stripped):
            used_funcs.add(func_match.group(1).strip().lower())

    if not used_funcs:
        return text

    needed: list[str] = []
    for lua_path in CORE_LUA_INITS:
        if lua_path.lower() not in existing_inits:
            needed.append(lua_path)

    for lua_path, funcs in EXTENSION_LUA_INITS.items():
        if lua_path.lower() not in existing_inits and used_funcs & funcs:
            needed.append(lua_path)

    if not needed:
        return text

    insert_idx = 0
    for idx, raw in enumerate(lines):
        stripped = raw.strip()
        if stripped.lower().startswith("--lua-init="):
            insert_idx = idx + 1
        elif insert_idx == 0 and (stripped.startswith("#") or stripped == ""):
            insert_idx = idx + 1

    new_lines = [f"--lua-init=@{lua_path}" for lua_path in needed]
    lines = [*lines[:insert_idx], *new_lines, *lines[insert_idx:]]
    return "\n".join(lines)


__all__ = [
    "CORE_LUA_INITS",
    "EXTENSION_LUA_INITS",
    "ensure_winws2_lua_init_lines",
    "has_winws2_strategy_tags",
    "is_winws2_circular_preset_source",
]
