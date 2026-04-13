from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional

from core.paths import AppPaths
from core.presets.strategy_catalog_sanitizer import sanitize_strategy_catalog_dir


@dataclass(frozen=True)
class StrategyEntry:
    strategy_id: str
    catalog_name: str
    name: str
    args: str


_ENSURE_SYNC_CACHE: dict[tuple[str, str], tuple[tuple[tuple[str, int, int], ...], str]] = {}
_STRATEGY_CATALOGS_CACHE: dict[
    tuple[str, str],
    tuple[tuple[tuple[str, int, int], ...], dict[str, dict[str, StrategyEntry]]],
] = {}


def _package_catalog_root() -> Path:
    return Path(__file__).resolve().parent / "catalogs"


def _user_catalog_root(paths: AppPaths) -> Path:
    return paths.user_root / "direct_preset" / "catalogs"


def ensure_user_catalogs(paths: AppPaths) -> Path:
    package_root = _package_catalog_root()
    user_root = _user_catalog_root(paths)
    user_root.mkdir(parents=True, exist_ok=True)

    for src in package_root.rglob("*.txt"):
        relative = src.relative_to(package_root)
        dst = user_root / relative
        src_text = src.read_text(encoding="utf-8", errors="replace")
        if dst.exists():
            dst_text = dst.read_text(encoding="utf-8", errors="replace")
            if dst_text == src_text:
                continue
        dst.parent.mkdir(parents=True, exist_ok=True)
        dst.write_text(src_text, encoding="utf-8")
    sanitize_strategy_catalog_dir(user_root / "winws1")
    sanitize_strategy_catalog_dir(user_root / "winws2")
    return user_root


def _tree_signature(root: Path, pattern: str = "*.txt") -> tuple[tuple[str, int, int], ...]:
    if not root.exists():
        return ()

    rows: list[tuple[str, int, int]] = []
    for path in sorted(root.rglob(pattern)):
        if not path.is_file():
            continue
        try:
            stat = path.stat()
            rel = path.relative_to(root).as_posix()
            rows.append((rel, int(getattr(stat, "st_mtime_ns", 0) or 0), int(getattr(stat, "st_size", 0) or 0)))
        except Exception:
            continue
    return tuple(rows)


def _ensure_user_catalogs_runtime(paths: AppPaths) -> Path:
    package_root = _package_catalog_root()
    user_root = _user_catalog_root(paths)
    cache_key = (str(package_root.resolve()), str(user_root.resolve()))
    package_signature = _tree_signature(package_root)
    cached = _ENSURE_SYNC_CACHE.get(cache_key)
    if cached is not None and cached[0] == package_signature and Path(cached[1]).exists():
        return Path(cached[1])

    ensured_root = ensure_user_catalogs(paths)
    _ENSURE_SYNC_CACHE[cache_key] = (package_signature, str(ensured_root))
    return ensured_root


def _parse_catalog_file(path: Path, catalog_name: str) -> dict[str, StrategyEntry]:
    strategies: dict[str, StrategyEntry] = {}
    current_id: Optional[str] = None
    current_name = ""
    current_args: list[str] = []

    def _flush() -> None:
        nonlocal current_id, current_name, current_args
        if not current_id:
            return
        strategies[current_id] = StrategyEntry(
            strategy_id=current_id,
            catalog_name=catalog_name,
            name=current_name or current_id,
            args="\n".join(line for line in current_args if line).strip(),
        )

    for raw in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = raw.rstrip()
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("[") and stripped.endswith("]"):
            _flush()
            current_id = stripped[1:-1].strip()
            current_name = current_id
            current_args = []
            continue
        if current_id is None:
            continue
        if stripped.startswith("--"):
            current_args.append(stripped)
            continue
        if "=" in stripped:
            key, _, value = stripped.partition("=")
            if key.strip().lower() == "name":
                current_name = value.strip()

    _flush()
    return strategies


def load_strategy_catalogs(paths: AppPaths, engine: str) -> dict[str, dict[str, StrategyEntry]]:
    root = _ensure_user_catalogs_runtime(paths)
    engine_root = root / engine
    cache_key = (str(engine_root.resolve()), str(engine or "").strip().lower())
    signature = _tree_signature(engine_root)
    cached = _STRATEGY_CATALOGS_CACHE.get(cache_key)
    if cached is not None and cached[0] == signature:
        return cached[1]

    catalogs: dict[str, dict[str, StrategyEntry]] = {}
    for path in sorted(engine_root.glob("*.txt")):
        catalogs[path.stem.lower()] = _parse_catalog_file(path, path.stem.lower())
    _STRATEGY_CATALOGS_CACHE[cache_key] = (signature, catalogs)
    return catalogs
