from __future__ import annotations

import os
from dataclasses import dataclass

from config import LOGS_FOLDER
from config.urls import BLOCKCHECK_DISCUSSIONS_URL
from log import global_logger, LOG_FILE
from support_request_bundle import PreparedSupportRequest, prepare_support_request


@dataclass(slots=True)
class SupportRequestFeedback:
    result: PreparedSupportRequest
    status_text: str
    info_text: str


def _build_feedback(result: PreparedSupportRequest) -> SupportRequestFeedback:
    status_parts: list[str] = []
    if result.zip_path:
        status_parts.append("ZIP готов")
    if result.copied_to_clipboard:
        status_parts.append("шаблон скопирован")
    if result.discussions_opened:
        status_parts.append("GitHub открыт")
    if result.bundle_folder_opened:
        status_parts.append("папка открыта")

    archive_name = os.path.basename(result.zip_path) if result.zip_path else "архив не создан"
    info_text = f"Архив: {archive_name}"
    if result.copied_to_clipboard:
        info_text += "\nШаблон обращения скопирован в буфер обмена."
    else:
        info_text += "\nШаблон не удалось скопировать автоматически."

    return SupportRequestFeedback(
        result=result,
        status_text=" • ".join(status_parts) or "Подготовка завершена",
        info_text=info_text,
    )


def _common_candidate_paths() -> list[str | None]:
    return [
        getattr(global_logger, "log_file", LOG_FILE),
    ]


def prepare_blockcheck_support_request(
    *,
    run_log_file: str | None,
    mode_label: str,
    extra_domains: list[str],
) -> SupportRequestFeedback:
    extra_note = (
        "В архив добавлен текущий лог запуска BlockCheck, если он уже был создан. "
        "Если вы добавляли свои домены, обязательно укажите в обращении, какие именно адреса дали TIMEOUT, FAIL или TCP_RESET."
    )
    if extra_domains:
        extra_note += f" Пользовательских доменов в запуске: {len(extra_domains)}."

    result = prepare_support_request(
        bundle_prefix="blockcheck_support",
        context_label=f"BlockCheck: {mode_label}",
        candidate_paths=[run_log_file, *_common_candidate_paths()],
        recent_patterns=("blockcheck_run_*.log", "zapret_winws2_debug_*.log"),
        extra_note=extra_note,
        discussions_url=BLOCKCHECK_DISCUSSIONS_URL,
    )
    return _build_feedback(result)


def prepare_strategy_scan_support_request(
    *,
    run_log_file: str | None,
    target: str,
    protocol_label: str,
    mode_label: str,
    resume_state_path: str | os.PathLike[str] | None,
    scan_protocol: str,
) -> SupportRequestFeedback:
    extra_note = (
        "В архив добавлен лог перебора стратегий, если он уже был создан. "
        f"Цель сканирования: {target}. Протокол: {protocol_label}. Режим: {mode_label}."
    )
    if scan_protocol == "udp_games":
        extra_note += (
            " Для UDP Games в обращении полезно отдельно указать, был ли выбран полный охват ipset или только игровые ipset."
        )

    result = prepare_support_request(
        bundle_prefix="strategy_scan_support",
        context_label=f"Подбор стратегии: {protocol_label} / {target}",
        candidate_paths=[
            run_log_file,
            *_common_candidate_paths(),
            str(resume_state_path) if resume_state_path is not None else None,
        ],
        recent_patterns=("blockcheck_run_*.log", "zapret_winws2_debug_*.log"),
        extra_note=extra_note,
        discussions_url=BLOCKCHECK_DISCUSSIONS_URL,
    )
    return _build_feedback(result)
