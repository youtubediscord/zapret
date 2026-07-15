"""Слоёное хранилище списков: base/user-слои и итоговый lists/<file>.

Владение итоговым файлом (`ListOwnership`) — явное понятие модуля:

- LAYERED  — итог принадлежит слоям: base- или user-слой содержит реальные
  записи, либо файлы слоёв существуют при итоге без реальных записей.
- EXTERNAL — слои без effective-записей, а lists/<file> содержит реальные
  записи: файлом управляет внешний источник (например, скачанный ipset-ru.txt
  при отсутствующей базе). Фоновая пересборка такой файл не трогает вовсе.
- ABSENT   — реальных записей нет нигде.

Пересборка разделена на три шага: снимок диска (`_load_snapshot`, все чтения),
чистое планирование (`_plan_rebuild`, ни одной IO-операции) и применение
(`_apply_plan`, все записи). Намерение выражается именем публичной функции:
`rebuild_*` — фоновая сверка с недеструктивным контрактом,
`write/delete/rename_*` и `create_*` — операции пользователя.
"""

from __future__ import annotations

import threading
from collections.abc import Iterable
from dataclasses import dataclass
from enum import Enum
from pathlib import Path, PureWindowsPath

from lists.core.builders import build_combined_content
from lists.core.files import normalize_newlines, read_text_file_safe, write_text_file

SAFE_HOSTLIST_PLACEHOLDER = "www.example.com"
SAFE_IPSET_PLACEHOLDER = "123.123.123.123"
_LAYERED_LIST_FILE_LOCK = threading.RLock()


class ListOwnership(Enum):
    LAYERED = "layered"
    EXTERNAL = "external"
    ABSENT = "absent"


@dataclass(frozen=True)
class LayeredListFile:
    file_name: str
    base_path: Path
    user_path: Path
    final_path: Path


@dataclass(frozen=True)
class _LayerSnapshot:
    """Однократный снимок состояния слоёв; дальше логика работает без диска."""

    base_exists: bool
    user_exists: bool
    base_entries: tuple[str, ...]
    user_entries: tuple[str, ...]
    user_text: str
    # Итог читается лениво: только когда слои без effective-записей и вопрос
    # владения реально стоит — иначе () без чтения (итог может быть большим).
    final_entries: tuple[str, ...]

    @property
    def ownership(self) -> ListOwnership:
        if self.layers_have_effective_entries:
            return ListOwnership.LAYERED
        if _has_effective_entries(self.final_entries):
            return ListOwnership.EXTERNAL
        if self.base_exists or self.user_exists:
            return ListOwnership.LAYERED
        return ListOwnership.ABSENT

    @property
    def layers_have_effective_entries(self) -> bool:
        return _has_effective_entries(self.base_entries) or _has_effective_entries(self.user_entries)


@dataclass(frozen=True)
class _RebuildPlan:
    """Решение пересборки; None/False — соответствующий шаг не выполняется."""

    write_user: str | None = None
    write_final: str | None = None
    unlink_final: bool = False


def layered_list_file(lists_root: Path, file_name: str) -> LayeredListFile:
    safe_name = safe_list_file_name(file_name)
    if not safe_name:
        raise ValueError("Не удалось определить имя файла списка.")
    root = Path(lists_root)
    return LayeredListFile(
        file_name=safe_name,
        base_path=root / "base" / safe_name,
        user_path=root / "user" / safe_name,
        final_path=root / safe_name,
    )


def safe_list_file_name(value: str) -> str:
    name = PureWindowsPath(str(value or "").replace("\\", "/")).name.strip()
    if not name or name in {".", ".."}:
        return ""
    return name


def create_profile_user_list_file(lists_root: Path, file_name: str) -> LayeredListFile:
    """Создаёт user-слой списка (операция пользователя: новый список).

    Сверка после создания — фоновая: пустой свежесозданный user-слой не даёт
    права затирать EXTERNAL-итог; содержимое утверждается первым сохранением.
    """
    with _LAYERED_LIST_FILE_LOCK:
        paths = layered_list_file(lists_root, file_name)
        if not paths.user_path.exists():
            write_text_file(str(paths.user_path), "")
        _reconcile_list_file(lists_root, file_name, authoritative=False)
        return paths


def read_profile_user_list_text(lists_root: Path, file_name: str) -> str:
    """Читает user-слой БЕЗ побочных эффектов.

    Read-путь не пишет на диск; user-слой материализуется при первом
    сохранении (write_profile_user_list_text) или создании списка
    (create_profile_user_list_file).
    """
    with _LAYERED_LIST_FILE_LOCK:
        paths = layered_list_file(lists_root, file_name)
        return read_text_file_safe(str(paths.user_path)) or ""


def write_profile_user_list_text(lists_root: Path, file_name: str, text: str) -> None:
    with _LAYERED_LIST_FILE_LOCK:
        paths = layered_list_file(lists_root, file_name)
        write_text_file(str(paths.user_path), text)
        _reconcile_list_file(lists_root, file_name, authoritative=True)


def rebuild_profile_list_file(lists_root: Path, file_name: str) -> None:
    """Фоновая пересборка lists/<file> из base- и user-слоёв.

    Контракт: EXTERNAL-итог (см. ListOwnership) не изменяется и не удаляется,
    плейсхолдер в user-слой не пишется. Деструктивная сверка возможна только
    из операций пользователя (write/delete/rename).
    """
    with _LAYERED_LIST_FILE_LOCK:
        _reconcile_list_file(lists_root, file_name, authoritative=False)


def rebuild_all_layered_list_files(lists_root: Path, *, user_only_file_names: Iterable[str] = ()) -> int:
    with _LAYERED_LIST_FILE_LOCK:
        root = Path(lists_root)
        base_names = _list_file_names(root / "base")
        user_names = _list_file_names(root / "user")
        allowed_user_only_names = {
            safe_name
            for raw_name in user_only_file_names
            if (safe_name := safe_list_file_name(str(raw_name or "")))
        }
        names = set(base_names)
        names.update(name for name in user_names if name in allowed_user_only_names)

        for name in sorted(names, key=str.casefold):
            _reconcile_list_file(root, name, authoritative=False)
        return len(names)


def profile_list_file_available(lists_root: Path, file_name: str) -> bool:
    paths = layered_list_file(lists_root, file_name)
    return paths.base_path.is_file() or paths.user_path.is_file() or paths.final_path.is_file()


def rename_profile_user_list_file(lists_root: Path, old_file_name: str, new_file_name: str) -> None:
    with _LAYERED_LIST_FILE_LOCK:
        old_paths = layered_list_file(lists_root, old_file_name) if safe_list_file_name(old_file_name) else None
        new_paths = layered_list_file(lists_root, new_file_name)
        new_paths.user_path.parent.mkdir(parents=True, exist_ok=True)
        if old_paths is not None and old_paths.user_path.exists() and old_paths.user_path != new_paths.user_path:
            if new_paths.user_path.exists():
                raise ValueError(f"Файл списка уже существует: {new_paths.file_name}")
            # Владение старым итогом фиксируется ДО переноса user-слоя: после
            # rename снимок уже не отличит слоёный итог от внешнего файла.
            old_was_external = _load_snapshot(old_paths).ownership is ListOwnership.EXTERNAL
            old_paths.user_path.rename(new_paths.user_path)
            # Старый итоговый файл был собран из унесённого user-слоя —
            # он обязан пересобраться/удалиться, а не остаться протухшим.
            # EXTERNAL-итог слоям не принадлежал — его не трогаем.
            _reconcile_list_file(lists_root, old_paths.file_name, authoritative=not old_was_external)
        elif not new_paths.user_path.exists():
            write_text_file(str(new_paths.user_path), "")
        # Новое имя сверяется фоново: перенесённый пустой user-слой не даёт
        # права затирать EXTERNAL-итог, уже живущий под этим именем.
        _reconcile_list_file(lists_root, new_paths.file_name, authoritative=False)


def delete_profile_user_list_file(lists_root: Path, file_name: str) -> None:
    with _LAYERED_LIST_FILE_LOCK:
        paths = layered_list_file(lists_root, file_name)
        # Владение определяется ДО удаления user-слоя: после unlink итог из
        # слоёв неотличим от внешнего (снимок видит только «файл с записями»).
        was_external = _load_snapshot(paths).ownership is ListOwnership.EXTERNAL
        try:
            paths.user_path.unlink()
        except FileNotFoundError:
            pass
        # EXTERNAL-итог (например, поставленный установщиком одноимённый список)
        # не принадлежал удаляемому user-слою — сверяем недеструктивно.
        _reconcile_list_file(lists_root, paths.file_name, authoritative=not was_external)


def _reconcile_list_file(lists_root: Path, file_name: str, *, authoritative: bool) -> None:
    """Снимок → план → применение. authoritative=True — операция пользователя:
    слои становятся единственным источником истины для итогового файла."""
    paths = layered_list_file(lists_root, file_name)
    snapshot = _load_snapshot(paths)
    plan = _plan_rebuild(paths.file_name, snapshot, authoritative=authoritative)
    _apply_plan(paths, plan)


def _load_snapshot(paths: LayeredListFile) -> _LayerSnapshot:
    base_exists = paths.base_path.is_file()
    user_exists = paths.user_path.is_file()
    base_entries = tuple(_text_entries(read_text_file_safe(str(paths.base_path)) or "")) if base_exists else ()
    user_text = (read_text_file_safe(str(paths.user_path)) or "") if user_exists else ""
    user_entries = tuple(_text_entries(user_text))
    if _has_effective_entries(base_entries) or _has_effective_entries(user_entries):
        # Слои владеют файлом — итог (потенциально большой) не читаем.
        final_entries: tuple[str, ...] = ()
    else:
        final_entries = tuple(_text_entries(read_text_file_safe(str(paths.final_path)) or ""))
    return _LayerSnapshot(
        base_exists=base_exists,
        user_exists=user_exists,
        base_entries=base_entries,
        user_entries=user_entries,
        user_text=user_text,
        final_entries=final_entries,
    )


def _plan_rebuild(file_name: str, snapshot: _LayerSnapshot, *, authoritative: bool) -> _RebuildPlan:
    if not authoritative and snapshot.ownership is ListOwnership.EXTERNAL:
        # Итогом управляет внешний источник — фоновая сверка его не трогает:
        # ни плейсхолдера в user-слой, ни перезаписи, ни удаления итога.
        return _RebuildPlan()

    user_text = snapshot.user_text
    user_entries = snapshot.user_entries
    write_user: str | None = None
    if not snapshot.layers_have_effective_entries and (snapshot.base_exists or snapshot.user_exists):
        # Существующий, но пустой список обязан остаться валидным для winws:
        # безопасный плейсхолдер сеется в user-слой и попадает в итог.
        placeholder = _safe_placeholder_for_list_file(file_name)
        user_text = _append_placeholder_to_text(user_text, placeholder)
        write_user = user_text
        user_entries = tuple(_text_entries(user_text))

    content = build_combined_content(list(snapshot.base_entries), list(user_entries))
    if not content and not snapshot.base_exists and not snapshot.user_exists:
        return _RebuildPlan(unlink_final=True)
    return _RebuildPlan(write_user=write_user, write_final=content)


def _apply_plan(paths: LayeredListFile, plan: _RebuildPlan) -> None:
    if plan.write_user is not None:
        write_text_file(str(paths.user_path), plan.write_user)
    if plan.unlink_final:
        try:
            paths.final_path.unlink()
        except FileNotFoundError:
            pass
        return
    if plan.write_final is not None:
        write_text_file(str(paths.final_path), plan.write_final)
        _verify_final_list_file(paths, plan.write_final)


def _safe_placeholder_for_list_file(file_name: str) -> str:
    return SAFE_IPSET_PLACEHOLDER if _is_ipset_file_name(file_name) else SAFE_HOSTLIST_PLACEHOLDER


def _is_ipset_file_name(file_name: str) -> bool:
    return safe_list_file_name(file_name).lower().startswith("ipset-")


def _list_file_names(folder: Path) -> set[str]:
    if not folder.is_dir():
        return set()
    return {
        safe_name
        for path in folder.glob("*.txt")
        if (safe_name := safe_list_file_name(path.name))
    }


def _verify_final_list_file(
    paths: LayeredListFile,
    expected_content: str,
) -> None:
    if not expected_content:
        return

    try:
        final_size = paths.final_path.stat().st_size
    except FileNotFoundError as exc:
        raise ValueError(
            f"Итоговый файл lists/{paths.file_name} не создан после пересборки."
        ) from exc

    if final_size == 0:
        raise ValueError(f"Итоговый файл lists/{paths.file_name} получился 0 КБ после пересборки.")


def _append_placeholder_to_text(text: str, placeholder: str) -> str:
    normalized = normalize_newlines(text)
    if not normalized:
        return placeholder
    return normalized + placeholder


def _has_effective_entries(entries: Iterable[str]) -> bool:
    return any(not entry.strip().startswith("#") for entry in entries)


def _text_entries(text: str) -> list[str]:
    result: list[str] = []
    for raw_line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if line:
            result.append(line)
    return result
