from __future__ import annotations

import glob
import os
import platform
import subprocess
import sys
import time
import webbrowser
import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from PyQt6.QtWidgets import QApplication

from config.build_info import APP_VERSION
from config.config import LOGS_FOLDER

from config.urls import SUPPORT_DISCUSSIONS_URL


@dataclass(slots=True)
class PreparedSupportRequest:
    zip_path: str | None
    included_files: list[str]
    template_text: str
    copied_to_clipboard: bool
    discussions_opened: bool
    bundle_folder_opened: bool


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
    files = _unique_existing_paths(candidate_paths)
    if not files:
        return None, []

    bundle_root = Path(output_dir) if output_dir else Path(LOGS_FOLDER) / "support_bundles"
    bundle_root.mkdir(parents=True, exist_ok=True)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    zip_name = f"{bundle_prefix}_{timestamp}.zip"
    zip_path = bundle_root / zip_name

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for file_path in files:
            archive.write(file_path, arcname=file_path.name)

    return str(zip_path), [path.name for path in files]


def build_support_template(
    *,
    context_label: str,
    zip_path: str | None,
    included_files: Sequence[str],
    extra_note: str = "",
) -> str:
    archive_line = zip_path or "ZIP не был создан"
    files_block = "\n".join(f"- {name}" for name in included_files) if included_files else "- Нет файлов"
    note_block = f"\nПримечание: {extra_note.strip()}" if extra_note.strip() else ""

    return (
        f"Заголовок: {context_label}\n"
        f"Версия приложения: Zapret2 v{APP_VERSION}\n"
        f"ОС: {platform.platform()}\n"
        f"Имя компьютера: {platform.node() or 'неизвестно'}\n"
        f"Время подготовки: {time.strftime('%d.%m.%Y %H:%M:%S')}\n"
        f"Архив с логами: {archive_line}\n"
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
    try:
        app = QApplication.instance()
        if app is None:
            return False
        clipboard = app.clipboard()
        if clipboard is None:
            return False
        clipboard.setText(text)
        return True
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
    zip_path, included_files = create_support_zip(
        bundle_prefix=bundle_prefix,
        candidate_paths=[*candidate_paths, *recent_files],
    )

    template_text = build_support_template(
        context_label=context_label,
        zip_path=zip_path,
        included_files=included_files,
        extra_note=extra_note,
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
    )
