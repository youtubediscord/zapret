"""Стабильная идентичность профилей: sidecar-реестр uid ↔ последний известный контент.

Единственное место в системе, где контент профиля участвует в идентичности.
Реестр хранится в settings (`profile_identity.<launch_method>`) и сопоставляет
uid последнему известному (имя, логическая match-сигнатура). Resolver чистый:
без I/O, без Qt, детерминированный — одинаковый вход даёт одинаковый выход.

Правила сопоставления (по убыванию силы, каждый uid используется не более
одного раза, профили обходятся в порядке следования в пресете, кандидаты-uid —
в лексикографическом порядке):

1. имя И сигнатура совпали — тот же профиль без изменений;
2. только сигнатура (непустая) — профиль переименовали;
3. только имя (непустое) — правили match-строки;
4. совпадений нет — новый uid.

Профили без имени и без match-строк (пустые name и sig) матчатся только
правилом 1 — слишком слабых привязок не делаем.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Sequence

UID_PREFIX = "uid:"


@dataclass(frozen=True)
class IdentityResolution:
    """Результат сопоставления парса с реестром.

    uids — по одному на профиль, в порядке входа; new_uids — впервые
    появившиеся; registry — следующий снапшот реестра (несопоставленные старые
    uid сохраняются: удалённый и возвращённый профиль снова получает свою мету).
    """

    uids: tuple[str, ...]
    new_uids: frozenset[str]
    registry: dict[str, dict[str, str]]


def generate_profile_uid() -> str:
    return f"{UID_PREFIX}{uuid.uuid4().hex}"


def is_profile_uid(value: object) -> bool:
    return str(value or "").startswith(UID_PREFIX)


def resolve_profile_identities(
    profiles: Sequence[tuple[str, str]],
    registry: Mapping[str, Any],
    *,
    generate_uid: Callable[[], str] = generate_profile_uid,
) -> IdentityResolution:
    """Сопоставляет профили парса (пары (имя, сигнатура) в порядке пресета)
    с реестром {uid: {"name": ..., "sig": ...}}."""
    entries = [(_clean(name), _clean(sig)) for name, sig in profiles]
    known = _normalize_registry(registry)

    claimed: set[str] = set()
    resolved: dict[int, str] = {}

    def match_pass(key_of_entry, key_of_meta) -> None:
        candidates: dict[str, list[str]] = {}
        for uid in sorted(known):
            if uid in claimed:
                continue
            key = key_of_meta(known[uid])
            if key is not None:
                candidates.setdefault(key, []).append(uid)
        for index, entry in enumerate(entries):
            if index in resolved:
                continue
            key = key_of_entry(entry)
            if key is None:
                continue
            bucket = candidates.get(key)
            if not bucket:
                continue
            uid = bucket.pop(0)
            claimed.add(uid)
            resolved[index] = uid

    # 1. Точное совпадение имени и сигнатуры.
    match_pass(lambda e: e, lambda m: (m["name"], m["sig"]))
    # 2. Только сигнатура (переименование); пустая сигнатура не является привязкой.
    match_pass(lambda e: e[1] or None, lambda m: m["sig"] or None)
    # 3. Только имя (правка match-строк); пустое имя не является привязкой.
    match_pass(lambda e: e[0] or None, lambda m: m["name"] or None)

    uids: list[str] = []
    new_uids: set[str] = set()
    for index in range(len(entries)):
        uid = resolved.get(index)
        if uid is None:
            uid = _clean(generate_uid()) or generate_profile_uid()
            while uid in known or uid in new_uids:
                uid = generate_profile_uid()
            new_uids.add(uid)
        uids.append(uid)

    next_registry = {uid: dict(meta) for uid, meta in known.items() if uid not in claimed}
    for index, uid in enumerate(uids):
        name, sig = entries[index]
        next_registry[uid] = {"name": name, "sig": sig}

    return IdentityResolution(uids=tuple(uids), new_uids=frozenset(new_uids), registry=next_registry)


def normalize_identity_registry(raw: object) -> dict[str, dict[str, str]]:
    """Нормализация снапшота реестра для settings: только uid-ключи с
    строковыми name/sig."""
    return _normalize_registry(raw)


def _normalize_registry(raw: object) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    if not isinstance(raw, Mapping):
        return result
    for raw_uid, raw_meta in raw.items():
        uid = _clean(raw_uid)
        if not uid or not isinstance(raw_meta, Mapping):
            continue
        result[uid] = {
            "name": _clean(raw_meta.get("name")),
            "sig": _clean(raw_meta.get("sig")),
        }
    return result


def _clean(value: object) -> str:
    return str(value or "").strip()


__all__ = [
    "IdentityResolution",
    "UID_PREFIX",
    "generate_profile_uid",
    "is_profile_uid",
    "normalize_identity_registry",
    "resolve_profile_identities",
]
