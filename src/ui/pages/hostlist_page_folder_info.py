"""Workflow/helper'ы информации по папкам hostlist/ipset."""

from __future__ import annotations

import threading


def normalize_folder_info_category(category: str) -> str:
    return "ipset" if category == "ipset" else "hostlist"


def build_folder_info_text(*, category: str, state, tr_fn) -> str:
    if not state.folder_exists:
        return tr_fn("page.hostlist.info.folder_not_found", "Папка листов не найдена")
    if category == "ipset":
        return tr_fn(
            "page.hostlist.info.ipset.summary",
            "📁 Папка: {folder}\n📄 IP-файлов: {files_count}\n🌐 Примерно IP/подсетей: {lines_count}",
            folder=state.folder,
            files_count=state.files_count,
            lines_count=f"{state.lines_count:,}",
        )
    return tr_fn(
        "page.hostlist.info.hostlist.summary",
        "📁 Папка: {folder}\n📄 Файлов: {files_count}\n📝 Примерно строк: {lines_count}",
        folder=state.folder,
        files_count=state.files_count,
        lines_count=f"{state.lines_count:,}",
    )


def build_folder_info_error_text(*, error: str, tr_fn) -> str:
    return tr_fn(
        "page.hostlist.info.error",
        "Ошибка загрузки информации: {error}",
        error=error,
    )


def request_folder_info(
    *,
    category: str,
    force: bool,
    request_seq_map: dict,
    loading_map: dict,
    loaded_map: dict,
    state_map: dict,
) -> tuple[bool, str, int]:
    normalized = normalize_folder_info_category(category)
    if loading_map[normalized] and not force:
        return False, normalized, int(request_seq_map[normalized])
    if loaded_map[normalized] and not force:
        return False, normalized, int(request_seq_map[normalized])

    request_seq_map[normalized] += 1
    request_seq = int(request_seq_map[normalized])
    loading_map[normalized] = True
    if force:
        loaded_map[normalized] = False
        state_map[normalized] = None
    return True, normalized, request_seq


def start_folder_info_thread(*, load_worker_fn, category: str, request_seq: int) -> None:
    worker = threading.Thread(
        target=load_worker_fn,
        args=(category, request_seq),
        daemon=True,
        name=f"HostlistPageInfo-{category}",
    )
    worker.start()


def accept_folder_info_loaded(
    *,
    category: str,
    request_seq: int,
    state,
    request_seq_map: dict,
    loading_map: dict,
    loaded_map: dict,
    state_map: dict,
) -> tuple[bool, str]:
    normalized = normalize_folder_info_category(category)
    if request_seq != request_seq_map.get(normalized):
        return False, normalized

    loading_map[normalized] = False
    loaded_map[normalized] = True
    state_map[normalized] = state
    return True, normalized


def accept_folder_info_failed(
    *,
    category: str,
    request_seq: int,
    request_seq_map: dict,
    loading_map: dict,
    loaded_map: dict,
    state_map: dict,
) -> tuple[bool, str]:
    normalized = normalize_folder_info_category(category)
    if request_seq != request_seq_map.get(normalized):
        return False, normalized

    loading_map[normalized] = False
    loaded_map[normalized] = False
    state_map[normalized] = None
    return True, normalized
