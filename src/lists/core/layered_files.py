"""Generic base/user/final storage for list files."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath

from lists.core.builders import build_combined_content
from lists.core.files import read_text_file_safe, write_text_file


@dataclass(frozen=True)
class LayeredListFile:
    file_name: str
    base_path: Path
    user_path: Path
    final_path: Path


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


def ensure_profile_user_list_file(lists_root: Path, file_name: str) -> LayeredListFile:
    paths = layered_list_file(lists_root, file_name)
    if paths.user_path.exists():
        return paths

    write_text_file(str(paths.user_path), "")
    rebuild_profile_list_file(lists_root, file_name)
    return paths


def read_profile_user_list_text(lists_root: Path, file_name: str) -> str:
    paths = ensure_profile_user_list_file(lists_root, file_name)
    return read_text_file_safe(str(paths.user_path)) or ""


def write_profile_user_list_text(lists_root: Path, file_name: str, text: str) -> None:
    paths = layered_list_file(lists_root, file_name)
    write_text_file(str(paths.user_path), text)
    rebuild_profile_list_file(lists_root, file_name)


def rebuild_profile_list_file(lists_root: Path, file_name: str) -> None:
    paths = layered_list_file(lists_root, file_name)
    base_entries = _text_entries(read_text_file_safe(str(paths.base_path)) or "")
    user_entries = _text_entries(read_text_file_safe(str(paths.user_path)) or "")
    content = build_combined_content(base_entries, user_entries)
    if not content and not paths.base_path.is_file() and not paths.user_path.is_file():
        try:
            paths.final_path.unlink()
        except FileNotFoundError:
            pass
        return
    write_text_file(str(paths.final_path), content)


def rebuild_all_layered_list_files(lists_root: Path) -> int:
    root = Path(lists_root)
    names: set[str] = set()
    for folder in (root / "base", root / "user"):
        if not folder.is_dir():
            continue
        for path in folder.glob("*.txt"):
            safe_name = safe_list_file_name(path.name)
            if safe_name:
                names.add(safe_name)

    for name in sorted(names, key=str.casefold):
        rebuild_profile_list_file(root, name)
    return len(names)


def profile_list_file_available(lists_root: Path, file_name: str) -> bool:
    paths = layered_list_file(lists_root, file_name)
    return paths.base_path.is_file() or paths.user_path.is_file() or paths.final_path.is_file()


def rename_profile_user_list_file(lists_root: Path, old_file_name: str, new_file_name: str) -> None:
    old_paths = layered_list_file(lists_root, old_file_name) if safe_list_file_name(old_file_name) else None
    new_paths = layered_list_file(lists_root, new_file_name)
    new_paths.user_path.parent.mkdir(parents=True, exist_ok=True)
    if old_paths is not None and old_paths.user_path.exists() and old_paths.user_path != new_paths.user_path:
        if new_paths.user_path.exists():
            raise ValueError(f"Файл списка уже существует: {new_paths.file_name}")
        old_paths.user_path.rename(new_paths.user_path)
        rebuild_profile_list_file(lists_root, old_paths.file_name)
    elif not new_paths.user_path.exists():
        write_text_file(str(new_paths.user_path), "")
    rebuild_profile_list_file(lists_root, new_paths.file_name)


def delete_profile_user_list_file(lists_root: Path, file_name: str) -> None:
    paths = layered_list_file(lists_root, file_name)
    try:
        paths.user_path.unlink()
    except FileNotFoundError:
        pass
    rebuild_profile_list_file(lists_root, paths.file_name)


def _text_entries(text: str) -> list[str]:
    result: list[str] = []
    for raw_line in str(text or "").replace("\r\n", "\n").replace("\r", "\n").split("\n"):
        line = raw_line.strip()
        if line:
            result.append(line)
    return result
