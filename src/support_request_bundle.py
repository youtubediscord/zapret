from __future__ import annotations

import glob
import os
import platform
import shutil
import subprocess
import sys
import time
import webbrowser
import zipfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from config.build_info import APP_VERSION
from config.runtime_layout import APPLICATION_PATHS

from config.urls import SUPPORT_DISCUSSIONS_URL


GITHUB_ATTACHMENT_LIMIT_BYTES = 25 * 1024 * 1024
SUPPORT_ARCHIVE_MAX_BYTES = GITHUB_ATTACHMENT_LIMIT_BYTES - 1024 * 1024
LOGS_FOLDER = str(APPLICATION_PATHS.logs_dir)


@dataclass(slots=True)
class PreparedSupportRequest:
    zip_path: str | None
    included_files: list[str]
    template_text: str
    copied_to_clipboard: bool
    discussions_opened: bool
    bundle_folder_opened: bool
    archive_paths: list[str] = field(default_factory=list)


@dataclass(slots=True)
class _SupportArchiveEntry:
    source_path: Path
    arcname: str
    offset: int
    size: int


def _unique_existing_paths(paths: Iterable[str | os.PathLike[str] | None]) -> list[Path]:
    result: list[Path] = []
    seen: set[str] = set()

    for raw_path in paths:
        if not raw_path:
            continue

        try:
            path = Path(raw_path).expanduser()
        except Exception:
            continue

        if not path.exists() or not path.is_file():
            continue

        key = str(path.resolve())
        if key in seen:
            continue

        seen.add(key)
        result.append(path)

    return result


def find_recent_logs(
    *,
    logs_folder: str | os.PathLike[str] = LOGS_FOLDER,
    patterns: Sequence[str] = (),
    limit_per_pattern: int = 1,
) -> list[Path]:
    recent_paths: list[Path] = []

    try:
        base = Path(logs_folder)
    except Exception:
        return recent_paths

    for pattern in patterns:
        try:
            matches = [
                Path(item)
                for item in glob.glob(str(base / pattern))
                if Path(item).is_file()
            ]
        except Exception:
            continue

        matches.sort(key=lambda item: item.stat().st_mtime, reverse=True)
        recent_paths.extend(matches[: max(0, int(limit_per_pattern))])

    return _unique_existing_paths(recent_paths)


def create_support_zip(
    *,
    bundle_prefix: str,
    candidate_paths: Iterable[str | os.PathLike[str] | None],
    output_dir: str | os.PathLike[str] | None = None,
) -> tuple[str | None, list[str]]:
    archive_paths, included_files = create_support_archives(
        bundle_prefix=bundle_prefix,
        candidate_paths=candidate_paths,
        output_dir=output_dir,
    )
    return (archive_paths[0] if archive_paths else None), included_files


def _part_arcname(path: Path, *, part_index: int, part_count: int) -> str:
    stem = path.stem or path.name
    suffix = path.suffix
    return f"{stem}.part{part_index:02d}-of-{part_count:02d}{suffix}"


def _archive_payload_limit(max_archive_bytes: int) -> int:
    max_bytes = max(1, int(max_archive_bytes))
    overhead = min(64 * 1024, max(1, max_bytes // 4))
    return max(1, max_bytes - overhead)


def _build_archive_entries(files: Sequence[Path], *, payload_limit: int) -> list[_SupportArchiveEntry]:
    entries: list[_SupportArchiveEntry] = []

    for file_path in files:
        try:
            file_size = max(0, int(file_path.stat().st_size))
        except OSError:
            continue

        if file_size <= payload_limit:
            entries.append(
                _SupportArchiveEntry(
                    source_path=file_path,
                    arcname=file_path.name,
                    offset=0,
                    size=file_size,
                )
            )
            continue

        part_count = (file_size + payload_limit - 1) // payload_limit
        for index in range(part_count):
            offset = index * payload_limit
            size = min(payload_limit, file_size - offset)
            entries.append(
                _SupportArchiveEntry(
                    source_path=file_path,
                    arcname=_part_arcname(file_path, part_index=index + 1, part_count=part_count),
                    offset=offset,
                    size=size,
                )
            )

    return entries


def _pack_archive_entries(
    entries: Sequence[_SupportArchiveEntry],
    *,
    payload_limit: int,
) -> list[list[_SupportArchiveEntry]]:
    packs: list[list[_SupportArchiveEntry]] = []
    current_pack: list[_SupportArchiveEntry] = []
    current_size = 0

    for entry in entries:
        entry_size = max(0, int(entry.size))
        if current_pack and current_size + entry_size > payload_limit:
            packs.append(current_pack)
            current_pack = []
            current_size = 0

        current_pack.append(entry)
        current_size += entry_size

    if current_pack:
        packs.append(current_pack)

    return packs


def _write_archive_entry(archive: zipfile.ZipFile, entry: _SupportArchiveEntry) -> None:
    if entry.offset == 0 and entry.size == entry.source_path.stat().st_size and entry.arcname == entry.source_path.name:
        archive.write(entry.source_path, arcname=entry.arcname)
        return

    with entry.source_path.open("rb") as source:
        source.seek(entry.offset)
        archive.writestr(entry.arcname, source.read(entry.size))


def create_support_archives(
    *,
    bundle_prefix: str,
    candidate_paths: Iterable[str | os.PathLike[str] | None],
    output_dir: str | os.PathLike[str] | None = None,
    max_archive_bytes: int = SUPPORT_ARCHIVE_MAX_BYTES,
) -> tuple[list[str], list[str]]:
    files = _unique_existing_paths(candidate_paths)
    if not files:
        return [], []

    bundle_root = Path(output_dir) if output_dir else Path(LOGS_FOLDER) / "support_bundles"
    bundle_root.mkdir(parents=True, exist_ok=True)

    payload_limit = _archive_payload_limit(max_archive_bytes)
    entries = _build_archive_entries(files, payload_limit=payload_limit)
    if not entries:
        return [], []

    packs = _pack_archive_entries(entries, payload_limit=payload_limit)
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    archive_paths: list[str] = []

    for index, pack in enumerate(packs, start=1):
        suffix = f"_part{index:02d}" if len(packs) > 1 else ""
        zip_path = bundle_root / f"{bundle_prefix}_{timestamp}{suffix}.zip"
        with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            for entry in pack:
                _write_archive_entry(archive, entry)
        archive_paths.append(str(zip_path))

    return archive_paths, [entry.arcname for entry in entries]


def build_support_template(
    *,
    context_label: str,
    zip_path: str | None,
    included_files: Sequence[str],
    extra_note: str = "",
    archive_paths: Sequence[str] | None = None,
) -> str:
    paths = [str(path) for path in (archive_paths or []) if str(path).strip()]
    if not paths and zip_path:
        paths = [zip_path]

    if len(paths) > 1:
        archive_block = "Архивы с логами:\n" + "\n".join(f"- {path}" for path in paths)
    else:
        archive_block = f"Архив с логами: {paths[0] if paths else 'ZIP не был создан'}"

    files_block = "\n".join(f"- {name}" for name in included_files) if included_files else "- Нет файлов"
    note_block = f"\nПримечание: {extra_note.strip()}" if extra_note.strip() else ""

    return (
        f"Заголовок: {context_label}\n"
        f"Версия приложения: Zapret2 v{APP_VERSION}\n"
        f"ОС: {platform.platform()}\n"
        f"Имя компьютера: {platform.node() or 'неизвестно'}\n"
        f"Время подготовки: {time.strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"{archive_block}\n"
        f"Вложенные файлы:\n{files_block}"
        f"{note_block}\n\n"
        "Что делал:\n"
        "- \n\n"
        "Что ожидал:\n"
        "- \n\n"
        "Что произошло на самом деле:\n"
        "- \n\n"
        "Дополнительные замечания:\n"
        "- "
    )


def _copy_to_clipboard(text: str) -> bool:
    value = str(text or "")
    if not value:
        return False
    if sys.platform == "win32":
        return _copy_to_clipboard_windows(value)
    if sys.platform == "darwin":
        return _copy_to_clipboard_command(["pbcopy"], value)

    for command in (
        ["wl-copy"],
        ["xclip", "-selection", "clipboard"],
        ["xsel", "--clipboard", "--input"],
        ["clip.exe"],
    ):
        if shutil.which(command[0]):
            return _copy_to_clipboard_command(command, value)
    return False


def _copy_to_clipboard_command(command: list[str], text: str) -> bool:
    try:
        completed = subprocess.run(
            command,
            input=text,
            text=True,
            capture_output=True,
            timeout=3,
            check=False,
        )
        return completed.returncode == 0
    except Exception:
        return False


def _copy_to_clipboard_windows(text: str) -> bool:
    try:
        import ctypes

        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
        kernel32.GlobalAlloc.argtypes = [ctypes.c_uint, ctypes.c_size_t]
        kernel32.GlobalAlloc.restype = ctypes.c_void_p
        kernel32.GlobalLock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalLock.restype = ctypes.c_void_p
        kernel32.GlobalUnlock.argtypes = [ctypes.c_void_p]
        kernel32.GlobalUnlock.restype = ctypes.c_int
        kernel32.GlobalFree.argtypes = [ctypes.c_void_p]
        kernel32.GlobalFree.restype = ctypes.c_void_p
        user32.OpenClipboard.argtypes = [ctypes.c_void_p]
        user32.OpenClipboard.restype = ctypes.c_int
        user32.EmptyClipboard.restype = ctypes.c_int
        user32.SetClipboardData.argtypes = [ctypes.c_uint, ctypes.c_void_p]
        user32.SetClipboardData.restype = ctypes.c_void_p
        user32.CloseClipboard.restype = ctypes.c_int

        encoded = (text + "\0").encode("utf-16le")
        handle = kernel32.GlobalAlloc(0x0002, len(encoded))
        if not handle:
            return False

        locked = kernel32.GlobalLock(handle)
        if not locked:
            kernel32.GlobalFree(handle)
            return False

        ctypes.memmove(locked, encoded, len(encoded))
        kernel32.GlobalUnlock(handle)

        if not user32.OpenClipboard(None):
            kernel32.GlobalFree(handle)
            return False

        handed_to_windows = False
        try:
            if not user32.EmptyClipboard():
                return False
            if not user32.SetClipboardData(13, handle):
                return False
            handed_to_windows = True
            return True
        finally:
            user32.CloseClipboard()
            if not handed_to_windows:
                kernel32.GlobalFree(handle)
    except Exception:
        return False


def _open_path(path: str) -> bool:
    try:
        if sys.platform == "win32":
            os.startfile(path)  # noqa: S606 - Windows only helper
            return True
        subprocess.Popen(["xdg-open", path])  # noqa: S603 - user-triggered opener
        return True
    except Exception:
        return False


def prepare_support_request(
    *,
    bundle_prefix: str,
    context_label: str,
    candidate_paths: Iterable[str | os.PathLike[str] | None],
    recent_patterns: Sequence[str] = (),
    extra_note: str = "",
    discussions_url: str | None = None,
    open_discussions: bool = True,
    open_bundle_folder: bool = True,
) -> PreparedSupportRequest:
    recent_files = find_recent_logs(patterns=recent_patterns)
    archive_paths, included_files = create_support_archives(
        bundle_prefix=bundle_prefix,
        candidate_paths=[*candidate_paths, *recent_files],
    )
    zip_path = archive_paths[0] if archive_paths else None

    template_text = build_support_template(
        context_label=context_label,
        zip_path=zip_path,
        included_files=included_files,
        extra_note=extra_note,
        archive_paths=archive_paths,
    )

    copied = _copy_to_clipboard(template_text)
    target_discussions_url = str(discussions_url or SUPPORT_DISCUSSIONS_URL).strip() or SUPPORT_DISCUSSIONS_URL
    discussions_opened = webbrowser.open(target_discussions_url) if open_discussions else False
    folder_opened = False
    if zip_path and open_bundle_folder:
        folder_opened = _open_path(str(Path(zip_path).parent))

    return PreparedSupportRequest(
        zip_path=zip_path,
        included_files=included_files,
        template_text=template_text,
        copied_to_clipboard=copied,
        discussions_opened=bool(discussions_opened),
        bundle_folder_opened=folder_opened,
        archive_paths=archive_paths,
    )
