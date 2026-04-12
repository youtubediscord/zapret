from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
from typing import Iterable, Optional, Set, Tuple

from config import get_zapret_userdata_dir


MarkKey = Tuple[str, str]  # (target_key, strategy_id)


def _get_marks_dir() -> Path:
    base = ""
    try:
        base = (get_zapret_userdata_dir() or "").strip()
    except Exception:
        base = ""

    if not base:
        appdata = (os.environ.get("APPDATA") or "").strip()
        if appdata:
            base = os.path.join(appdata, "zapret")

    if not base:
        raise RuntimeError("APPDATA is required for strategy marks storage")

    # Папка пользовательских данных пока сохранена прежней, чтобы не потерять уже
    # записанные оценки и избранное после переноса store-слоя из старой архитектуры.
    return Path(base) / "direct_zapret2"


def _parse_marks_lines(lines: Iterable[str]) -> Set[MarkKey]:
    out: Set[MarkKey] = set()
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "\t" not in line:
            continue
        cat, sid = line.split("\t", 1)
        cat = cat.strip()
        sid = sid.strip()
        if cat and sid:
            out.add((cat, sid))
    return out


def _format_marks_lines(keys: Set[MarkKey]) -> str:
    parts = [f"{cat}\t{sid}" for cat, sid in sorted(keys, key=lambda x: (x[0].lower(), x[1].lower()))]
    return ("\n".join(parts) + "\n") if parts else ""


@dataclass
class StrategyMarksStore:
    work_path: Path
    notwork_path: Path
    _work: Optional[Set[MarkKey]] = None
    _notwork: Optional[Set[MarkKey]] = None

    @classmethod
    def default(cls) -> "StrategyMarksStore":
        base = _get_marks_dir()
        return cls(work_path=base / "work.txt", notwork_path=base / "notwork.txt")

    def reset_cache(self) -> None:
        self._work = None
        self._notwork = None

    def _ensure_loaded(self) -> None:
        if self._work is not None and self._notwork is not None:
            return
        self._work = set()
        self._notwork = set()

        if self.work_path.exists():
            self._work = _parse_marks_lines(self.work_path.read_text(encoding="utf-8", errors="ignore").splitlines())
        if self.notwork_path.exists():
            self._notwork = _parse_marks_lines(self.notwork_path.read_text(encoding="utf-8", errors="ignore").splitlines())

        self._notwork.difference_update(self._work)

    def get_mark(self, target_key: str, strategy_id: str) -> Optional[bool]:
        self._ensure_loaded()
        key = (target_key, strategy_id)
        if key in self._work:
            return True
        if key in self._notwork:
            return False
        return None

    def get_rating(self, strategy_id: str, target_key: str | None = None) -> str | None:
        sid = str(strategy_id or "").strip()
        if not sid:
            return None
        if target_key:
            mark = self.get_mark(str(target_key).strip(), sid)
            if mark is True:
                return "working"
            if mark is False:
                return "broken"
            return None

        for _category, ratings in self.export_ratings().items():
            if sid in ratings:
                return ratings[sid]
        return None

    def set_mark(self, target_key: str, strategy_id: str, is_working: Optional[bool]) -> None:
        self._ensure_loaded()
        key = (target_key, strategy_id)
        self._work.discard(key)
        self._notwork.discard(key)
        if is_working is True:
            self._work.add(key)
        elif is_working is False:
            self._notwork.add(key)
        self._save()

    def set_rating(self, strategy_id: str, rating: str | None, target_key: str | None = None) -> bool:
        normalized_target = str(target_key or "").strip()
        if not normalized_target:
            return False

        normalized = str(rating or "").strip().lower()
        mark: Optional[bool]
        if not normalized:
            mark = None
        elif normalized == "working":
            mark = True
        elif normalized == "broken":
            mark = False
        else:
            return False

        self.set_mark(normalized_target, str(strategy_id or "").strip(), mark)
        return True

    def toggle_rating(self, strategy_id: str, rating: str, target_key: str | None = None) -> str | None:
        current = self.get_rating(strategy_id, target_key)
        if current == rating:
            self.set_rating(strategy_id, None, target_key)
            return None
        if self.set_rating(strategy_id, rating, target_key):
            return str(rating or "").strip().lower() or None
        return current

    def export_ratings(self) -> dict[str, dict[str, str]]:
        self._ensure_loaded()
        ratings: dict[str, dict[str, str]] = {}
        for cat, sid in self._work:
            ratings.setdefault(cat, {})[sid] = "working"
        for cat, sid in self._notwork:
            ratings.setdefault(cat, {})[sid] = "broken"
        return ratings

    def _save(self) -> None:
        base = self.work_path.parent
        base.mkdir(parents=True, exist_ok=True)
        self.work_path.write_text(_format_marks_lines(self._work or set()), encoding="utf-8")
        self.notwork_path.write_text(_format_marks_lines(self._notwork or set()), encoding="utf-8")


@dataclass
class StrategyFavoritesStore:
    favorites_path: Path
    _favorites: Optional[Set[MarkKey]] = None

    @classmethod
    def default(cls) -> "StrategyFavoritesStore":
        base = _get_marks_dir()
        return cls(favorites_path=base / "favorites.txt")

    def reset_cache(self) -> None:
        self._favorites = None

    def _ensure_loaded(self) -> None:
        if self._favorites is not None:
            return
        self._favorites = set()
        if self.favorites_path.exists():
            self._favorites = _parse_marks_lines(self.favorites_path.read_text(encoding="utf-8", errors="ignore").splitlines())

    def get_favorites(self, target_key: str) -> Set[str]:
        self._ensure_loaded()
        cat = (target_key or "").strip()
        if not cat:
            return set()
        return {sid for c, sid in (self._favorites or set()) if c == cat}

    def is_favorite(self, target_key: str, strategy_id: str) -> bool:
        self._ensure_loaded()
        return (target_key, strategy_id) in (self._favorites or set())

    def set_favorite(self, target_key: str, strategy_id: str, favorite: bool) -> None:
        self._ensure_loaded()
        key = ((target_key or "").strip(), (strategy_id or "").strip())
        if not key[0] or not key[1]:
            return
        if favorite:
            self._favorites.add(key)
        else:
            self._favorites.discard(key)
        self._save()

    def toggle_favorite(self, target_key: str, strategy_id: str) -> bool:
        favorite = not self.is_favorite(target_key, strategy_id)
        self.set_favorite(target_key, strategy_id, favorite)
        return favorite

    def _save(self) -> None:
        base = self.favorites_path.parent
        base.mkdir(parents=True, exist_ok=True)
        self.favorites_path.write_text(_format_marks_lines(self._favorites or set()), encoding="utf-8")
