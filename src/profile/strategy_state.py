from __future__ import annotations

import threading
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from settings import store as settings_store


VALID_RATINGS = frozenset({"", "work", "notwork"})

# Мутации — read-modify-write над общим settings.json и зовутся из разных
# QThread-воркеров (save-воркеры мигрируют ключ, оценки пишутся из feedback-
# воркеров). _read()/_write() атомарны по отдельности, связка — нет: без
# общего лока интерлив теряет рейтинг или мигрированную мету. Паттерн — как
# _PROFILE_FOLDER_STATE_LOCK в folders.py.
_PROFILE_STRATEGY_STATE_LOCK = threading.RLock()


@dataclass(frozen=True)
class ProfileStrategyState:
    rating: str = ""
    favorite: bool = False


class ProfileStrategyStateStore:
    """Хранит оценки готовых стратегий профилей в общем settings.json."""

    @property
    def path(self) -> Path:
        return settings_store.get_settings_path()

    def get_strategy_state(self, profile_key: str, strategy_id: str) -> ProfileStrategyState:
        states = self.get_strategy_states(profile_key, (strategy_id,))
        return states.get(_normalize_strategy_id(strategy_id), ProfileStrategyState())

    def get_strategy_states(self, profile_key: str, strategy_ids) -> dict[str, ProfileStrategyState]:
        clean_profile_key = _normalize_profile_key(profile_key)
        clean_strategy_ids = tuple(
            strategy_id
            for strategy_id in (_normalize_strategy_id(value) for value in tuple(strategy_ids or ()))
            if strategy_id
        )
        if not clean_profile_key or not clean_strategy_ids:
            return {}

        data = self._read()
        return {
            strategy_id: _state_from_row(_strategy_row(data, clean_profile_key, strategy_id))
            for strategy_id in clean_strategy_ids
        }

    def set_strategy_state(
        self,
        profile_key: str,
        strategy_id: str,
        *,
        rating: str | None = None,
        favorite: bool | None = None,
    ) -> ProfileStrategyState:
        clean_profile_key = _normalize_profile_key(profile_key)
        clean_strategy_id = _normalize_strategy_id(strategy_id)
        if not clean_profile_key:
            raise ValueError("profile key is required")
        if not clean_strategy_id:
            raise ValueError("strategy id is required")

        with _PROFILE_STRATEGY_STATE_LOCK:
            data = self._read()
            current_state = _state_from_row(_strategy_row(data, clean_profile_key, clean_strategy_id))
            next_state = ProfileStrategyState(
                rating=_normalize_rating(rating) if rating is not None else current_state.rating,
                favorite=bool(favorite) if favorite is not None else current_state.favorite,
            )
            if next_state == current_state:
                return current_state

            profiles = data.setdefault("profiles", {})
            if not isinstance(profiles, dict):
                profiles = {}
                data["profiles"] = profiles

            profile_row = profiles.setdefault(clean_profile_key, {})
            if not isinstance(profile_row, dict):
                profile_row = {}
                profiles[clean_profile_key] = profile_row

            strategies = profile_row.setdefault("strategies", {})
            if not isinstance(strategies, dict):
                strategies = {}
                profile_row["strategies"] = strategies

            row = strategies.setdefault(clean_strategy_id, {})
            if not isinstance(row, dict):
                row = {}
                strategies[clean_strategy_id] = row

            if rating is not None:
                row["rating"] = _normalize_rating(rating)
            if favorite is not None:
                row["favorite"] = bool(favorite)
            row["updated_at"] = _now_iso()

            if not row.get("rating") and not bool(row.get("favorite")):
                strategies.pop(clean_strategy_id, None)
            if not strategies:
                profiles.pop(clean_profile_key, None)

            self._write(data)
            return self.get_strategy_state(clean_profile_key, clean_strategy_id)

    def migrate_profile_key(self, old_profile_key: str, new_profile_key: str) -> bool:
        """Переносит записи стратегий `profiles[old]` → `profiles[new]` при
        смене persistent_key профиля (правка имени/match-строк).

        Правило слияния: существующие записи нового ключа имеют приоритет и
        не затираются; отсутствующие копируются со старого ключа. Старый ключ
        удаляется. Возвращает True, если хранилище было изменено; при
        old == new или отсутствии старого ключа запись не производится."""
        old_key = _normalize_profile_key(old_profile_key)
        new_key = _normalize_profile_key(new_profile_key)
        if not old_key or not new_key or old_key == new_key:
            return False

        with _PROFILE_STRATEGY_STATE_LOCK:
            data = self._read()
            profiles = data.get("profiles")
            if not isinstance(profiles, dict) or old_key not in profiles:
                return False

            old_row = profiles.pop(old_key)
            old_strategies = old_row.get("strategies") if isinstance(old_row, dict) else None
            if isinstance(old_strategies, dict) and old_strategies:
                new_row = profiles.get(new_key)
                if not isinstance(new_row, dict):
                    new_row = {}
                    profiles[new_key] = new_row
                new_strategies = new_row.get("strategies")
                if not isinstance(new_strategies, dict):
                    new_strategies = {}
                    new_row["strategies"] = new_strategies
                for strategy_id, row in old_strategies.items():
                    new_strategies.setdefault(strategy_id, row)

            self._write(data)
            return True

    def clear_strategy_state(self, profile_key: str, strategy_id: str) -> None:
        clean_profile_key = _normalize_profile_key(profile_key)
        clean_strategy_id = _normalize_strategy_id(strategy_id)
        if not clean_profile_key or not clean_strategy_id:
            return

        with _PROFILE_STRATEGY_STATE_LOCK:
            data = self._read()
            profiles = data.get("profiles")
            if not isinstance(profiles, dict):
                return
            profile_row = profiles.get(clean_profile_key)
            if not isinstance(profile_row, dict):
                return
            strategies = profile_row.get("strategies")
            if not isinstance(strategies, dict):
                return
            if clean_strategy_id not in strategies:
                return

            strategies.pop(clean_strategy_id, None)
            if not strategies:
                profiles.pop(clean_profile_key, None)
            self._write(data)

    def _read(self) -> dict[str, Any]:
        raw = settings_store.get_profile_strategy_state_settings()
        if not isinstance(raw, dict):
            return _empty_state()
        raw["version"] = 1
        raw.setdefault("profiles", {})
        return raw

    def _write(self, data: dict[str, Any]) -> None:
        settings_store.set_profile_strategy_state_settings(_normalize_data(data))


def _empty_state() -> dict[str, Any]:
    return {
        "version": 1,
        "profiles": {},
    }


def _normalize_data(data: dict[str, Any]) -> dict[str, Any]:
    raw_profiles = data.get("profiles")
    profiles: dict[str, Any] = {}
    if isinstance(raw_profiles, dict):
        for raw_profile_key, raw_profile_row in raw_profiles.items():
            profile_key = _normalize_profile_key(raw_profile_key)
            if not profile_key or not isinstance(raw_profile_row, dict):
                continue
            raw_strategies = raw_profile_row.get("strategies")
            if not isinstance(raw_strategies, dict):
                continue
            strategies: dict[str, Any] = {}
            for raw_strategy_id, raw_strategy_row in raw_strategies.items():
                strategy_id = _normalize_strategy_id(raw_strategy_id)
                if not strategy_id or not isinstance(raw_strategy_row, dict):
                    continue
                rating = _normalize_rating(raw_strategy_row.get("rating"))
                favorite = bool(raw_strategy_row.get("favorite"))
                if not rating and not favorite:
                    continue
                row: dict[str, Any] = {
                    "favorite": favorite,
                    "rating": rating,
                }
                updated_at = str(raw_strategy_row.get("updated_at") or "").strip()
                if updated_at:
                    row["updated_at"] = updated_at
                strategies[strategy_id] = row
            if strategies:
                profiles[profile_key] = {"strategies": strategies}

    return {
        "version": 1,
        "profiles": profiles,
    }


def _strategy_row(data: dict[str, Any], profile_key: str, strategy_id: str) -> dict[str, Any]:
    profiles = data.get("profiles")
    if not isinstance(profiles, dict):
        return {}
    profile_row = profiles.get(_normalize_profile_key(profile_key))
    if not isinstance(profile_row, dict):
        return {}
    strategies = profile_row.get("strategies")
    if not isinstance(strategies, dict):
        return {}
    row = strategies.get(_normalize_strategy_id(strategy_id))
    return row if isinstance(row, dict) else {}


def _state_from_row(row: dict[str, Any]) -> ProfileStrategyState:
    return ProfileStrategyState(
        rating=_normalize_rating(row.get("rating") if isinstance(row, dict) else ""),
        favorite=bool(row.get("favorite")) if isinstance(row, dict) else False,
    )


def _normalize_profile_key(value: object) -> str:
    text = str(value or "").strip()
    if text.startswith("name:") or text.startswith("sig:"):
        return text
    return ""


def _normalize_strategy_id(value: object) -> str:
    text = str(value or "").strip()
    if text in {"", "none", "custom"}:
        return ""
    return text


def _normalize_rating(value: object) -> str:
    rating = str(value or "").strip().lower()
    return rating if rating in VALID_RATINGS else ""


def _now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
