from __future__ import annotations

from pathlib import Path

from app.text_catalog import tr as tr_catalog
from blockcheck.strategy_scan_resume import clear_resume_state, get_resume_index, save_resume_state, scan_key
from blockcheck.strategy_scan_state import (
    StrategyApplyResult,
    StrategyScanFinishPlan,
    StrategyScanInteractionPlan,
    StrategyScanLanguagePlan,
    StrategyScanLogExpandPlan,
    StrategyScanNotificationPlan,
    StrategyScanProgressPlan,
    StrategyScanProtocolUiPlan,
    StrategyScanQuickMenuPlan,
    StrategyScanResultPresentation,
    StrategyScanStartPlan,
    StrategyScanSupportContext,
    StrategyScanUiMessagePlan,
    StrategyScanUdpHintPlan,
)
from blockcheck.strategy_scan_targeting import (
    default_target_for_protocol,
    load_quick_domains,
    load_quick_stun_targets,
    normalize_target_input,
    resolve_games_ipset_paths,
    scan_protocol_from_value,
)

def build_protocol_ui_plan(*, scan_protocol: str, current_value: str) -> StrategyScanProtocolUiPlan:
    current = str(current_value or "")
    is_udp_games = scan_protocol == "udp_games"
    show_target_controls = scan_protocol != "udp_games"

    if scan_protocol in {"stun_voice", "udp_games"} and current and ":" not in current and not current.upper().startswith("STUN:"):
        current = ""

    normalized = normalize_target_input(current, scan_protocol)
    if not normalized:
        normalized = default_target_for_protocol(scan_protocol)

    return StrategyScanProtocolUiPlan(
        scan_protocol=scan_protocol,
        is_udp_games=is_udp_games,
        show_target_controls=show_target_controls,
        normalized_target=normalized,
        placeholder_text=default_target_for_protocol(scan_protocol),
    )


def build_udp_scope_hint_plan(
    *,
    scan_protocol: str,
    udp_games_scope: str,
    scope_all_label: str,
    scope_games_only_label: str,
) -> StrategyScanUdpHintPlan:
    if scan_protocol != "udp_games":
        return StrategyScanUdpHintPlan(
            visible=False,
            text="",
            tooltip="",
        )

    paths = resolve_games_ipset_paths(udp_games_scope)
    scope_label = scope_games_only_label if udp_games_scope == "games_only" else scope_all_label

    short_names = [Path(p).name or p for p in paths]
    preview = ", ".join(short_names[:4])
    if len(short_names) > 4:
        preview += f", ... (+{len(short_names) - 4})"

    return StrategyScanUdpHintPlan(
        visible=True,
        text=f"UDP scope: {scope_label} | ipset files: {len(paths)} | {preview}",
        tooltip="\n".join(paths),
    )


def build_quick_target_menu_plan(*, scan_protocol: str, current_value: str) -> StrategyScanQuickMenuPlan:
    current = normalize_target_input(current_value, scan_protocol)
    options = load_quick_domains() if scan_protocol == "tcp_https" else load_quick_stun_targets()
    return StrategyScanQuickMenuPlan(
        options=options,
        current_value=current,
    )


def build_running_interaction_plan() -> StrategyScanInteractionPlan:
    return StrategyScanInteractionPlan(
        start_enabled=False,
        stop_enabled=True,
        protocol_enabled=False,
        games_scope_enabled=False,
        mode_enabled=False,
        target_enabled=False,
        quick_domain_enabled=False,
    )


def build_idle_interaction_plan(*, is_udp_games: bool) -> StrategyScanInteractionPlan:
    return StrategyScanInteractionPlan(
        start_enabled=True,
        stop_enabled=False,
        protocol_enabled=True,
        games_scope_enabled=bool(is_udp_games),
        mode_enabled=True,
        target_enabled=True,
        quick_domain_enabled=True,
    )


def build_log_expand_plan(*, expanded: bool, language: str) -> StrategyScanLogExpandPlan:
    if expanded:
        return StrategyScanLogExpandPlan(
            control_visible=False,
            warning_visible=False,
            results_visible=False,
            log_min_height=400,
            log_max_height=16777215,
            button_text=tr_catalog("page.strategy_scan.collapse_log", language=language, default="Свернуть"),
        )
    return StrategyScanLogExpandPlan(
        control_visible=True,
        warning_visible=True,
        results_visible=True,
        log_min_height=180,
        log_max_height=300,
        button_text=tr_catalog("page.strategy_scan.expand_log", language=language, default="Развернуть"),
    )


def build_language_plan(*, language: str, log_expanded: bool) -> StrategyScanLanguagePlan:
    return StrategyScanLanguagePlan(
        control_title=tr_catalog("page.strategy_scan.control", language=language, default="Управление сканированием"),
        results_title=tr_catalog("page.strategy_scan.results", language=language, default="Результаты"),
        log_title=tr_catalog("page.strategy_scan.log", language=language, default="Подробный лог"),
        expand_log_text=(
            tr_catalog("page.strategy_scan.collapse_log", language=language, default="Свернуть")
            if log_expanded
            else tr_catalog("page.strategy_scan.expand_log", language=language, default="Развернуть")
        ),
        warning_title=tr_catalog("page.strategy_scan.warning_title", language=language, default="Внимание"),
        start_text=tr_catalog("page.strategy_scan.start", language=language, default="Начать сканирование"),
        stop_text=tr_catalog("page.strategy_scan.stop", language=language, default="Остановить"),
        prepare_support_text=tr_catalog(
            "page.strategy_scan.prepare_support",
            language=language,
            default="Подготовить обращение",
        ),
        protocol_items=[
            tr_catalog("page.strategy_scan.protocol_tcp", language=language, default="TCP/HTTPS"),
            tr_catalog(
                "page.strategy_scan.protocol_stun",
                language=language,
                default="STUN Voice (Discord/Telegram)",
            ),
            tr_catalog(
                "page.strategy_scan.protocol_games",
                language=language,
                default="UDP Games (Roblox/Amazon/Steam)",
            ),
        ],
        udp_scope_label=tr_catalog("page.strategy_scan.udp_scope", language=language, default="Охват UDP:"),
        udp_scope_items=[
            tr_catalog(
                "page.strategy_scan.udp_scope_all",
                language=language,
                default="Все ipset (по умолчанию)",
            ),
            tr_catalog(
                "page.strategy_scan.udp_scope_games_only",
                language=language,
                default="Только игровые ipset",
            ),
        ],
        quick_domains_text=tr_catalog("page.strategy_scan.quick_domains", language=language, default="Быстрый выбор"),
        quick_domains_tooltip=tr_catalog(
            "page.strategy_scan.quick_domains_hint",
            language=language,
            default="Выберите домен из готового списка",
        ),
    )


def build_apply_success_plan(result: StrategyApplyResult) -> StrategyScanUiMessagePlan:
    operation = str(getattr(result, "operation", "") or "").strip().lower()
    if operation == "updated":
        title_default = "Стратегия обновлена"
        body_text = f"{result.strategy_name} заменена в существующем profile: {result.applied_profile}"
    else:
        title_default = "Стратегия применена"
        body_text = f"{result.strategy_name} применена к profile: {result.applied_profile}"
    return StrategyScanUiMessagePlan(
        kind="success",
        title_key="page.strategy_scan.applied",
        title_default=title_default,
        body_text=body_text,
    )


def build_apply_error_plan(error_text: str) -> StrategyScanUiMessagePlan:
    return StrategyScanUiMessagePlan(
        kind="warning",
        title_key="common.error",
        title_default="Ошибка",
        body_text=str(error_text or ""),
    )


def build_support_success_plan(feedback) -> StrategyScanUiMessagePlan:
    return StrategyScanUiMessagePlan(
        kind="success",
        title_key="page.strategy_scan.support_prepared_title",
        title_default="Обращение подготовлено",
        body_text=str(getattr(feedback, "info_text", "") or ""),
        status_text=str(getattr(feedback, "status_text", "") or ""),
    )


def build_support_error_plan(error_text: str) -> StrategyScanUiMessagePlan:
    return StrategyScanUiMessagePlan(
        kind="warning",
        title_key="page.strategy_scan.error",
        title_default="Ошибка сканирования",
        body_text=f"Не удалось подготовить обращение:\n{error_text}",
        status_text="Ошибка подготовки",
    )


def build_support_context(
    *,
    stored_scan_protocol: str,
    stored_scan_target: str,
    raw_protocol_value,
    raw_target_input: str,
    raw_protocol_label: str,
    raw_mode_label: str,
    stored_mode: str,
) -> StrategyScanSupportContext:
    scan_protocol = stored_scan_protocol or scan_protocol_from_value(raw_protocol_value)
    target = stored_scan_target or normalize_target_input(raw_target_input, scan_protocol)
    if not target:
        target = default_target_for_protocol(scan_protocol)

    protocol_label = str(raw_protocol_label or "").strip() or scan_protocol
    mode_label = str(raw_mode_label or "").strip() or str(stored_mode or "")
    return StrategyScanSupportContext(
        scan_protocol=scan_protocol,
        target=target,
        protocol_label=protocol_label,
        mode_label=mode_label,
    )


def count_working_results(result_rows: list[dict]) -> int:
    return sum(1 for row in result_rows if row.get("success"))


def build_progress_plan(
    *,
    strategy_name: str,
    index: int,
    total: int,
    result_rows: list[dict],
) -> StrategyScanProgressPlan:
    working = count_working_results(result_rows)
    return StrategyScanProgressPlan(
        total=max(0, int(total)),
        status_text=f"[{index + 1}/{total}] {strategy_name}  |  {working} рабочих",
    )


def build_result_presentation(result, *, scan_cursor: int) -> StrategyScanResultPresentation:
    tip_parts = [result.strategy_args]
    if result.error:
        tip_parts.append(f"\n--- Ошибка ---\n{result.error}")

    error_text = str(getattr(result, "error", "") or "")
    error_lower = error_text.lower()
    if result.success:
        status_text = "OK"
        status_tone = "success"
    elif "timeout" in error_lower:
        status_text = "TIMEOUT"
        status_tone = "timeout"
    else:
        status_text = "FAIL"
        status_tone = "fail"

    time_ms = float(getattr(result, "time_ms", 0) or 0)
    time_text = f"{time_ms:.0f}" if time_ms > 0 else "—"

    return StrategyScanResultPresentation(
        number_text=str(scan_cursor + 1),
        strategy_name=result.strategy_name,
        strategy_tooltip="".join(tip_parts),
        status_text=status_text,
        status_tone=status_tone,
        status_tooltip=error_text if error_text else "OK",
        time_text=time_text,
        can_apply=bool(result.success),
        stored_row={
            "id": getattr(result, "strategy_id", ""),
            "name": result.strategy_name,
            "args": result.strategy_args,
            "success": bool(result.success),
        },
    )


def plan_scan_start(
    *,
    raw_target_input: str,
    scan_protocol: str,
    udp_games_scope: str,
    mode: str,
    previous_target: str,
    previous_protocol: str,
    previous_scope: str,
    result_rows_count: int,
    table_row_count: int,
    starting_status_text: str,
) -> StrategyScanStartPlan:
    target = normalize_target_input(raw_target_input, scan_protocol)
    if not target:
        target = default_target_for_protocol(scan_protocol)

    prev_scan_key = scan_key(previous_target, previous_protocol, previous_scope)
    scan_key = scan_key(target, scan_protocol, udp_games_scope)

    resume_next_index = get_resume_index(target, scan_protocol, udp_games_scope)
    resume_available = resume_next_index > 0

    keep_current_results = (
        resume_available
        and previous_protocol == scan_protocol
        and previous_scope == udp_games_scope
        and prev_scan_key == scan_key
        and result_rows_count == resume_next_index
        and table_row_count == result_rows_count
    )

    scan_cursor = resume_next_index if resume_available else 0
    if resume_available:
        status_text = f"Возобновление сканирования с [{scan_cursor + 1}]..."
    else:
        status_text = starting_status_text

    return StrategyScanStartPlan(
        target=target,
        scan_protocol=scan_protocol,
        udp_games_scope=udp_games_scope,
        mode=mode,
        keep_current_results=keep_current_results,
        scan_cursor=scan_cursor,
        status_text=status_text,
    )


def finalize_scan_report(
    report,
    *,
    scan_target: str,
    scan_protocol: str,
    scan_udp_games_scope: str,
    scan_mode: str,
    scan_cursor: int,
    result_rows: list[dict],
) -> StrategyScanFinishPlan:
    working = sum(1 for row in result_rows if row.get("success"))

    if report is None:
        if scan_cursor > 0:
            save_resume_state(
                scan_target,
                scan_protocol,
                scan_cursor,
                scan_udp_games_scope,
            )
        return StrategyScanFinishPlan(
            total_available=0,
            working_count=working,
            total_count=scan_cursor,
            cancelled=False,
            baseline_accessible=False,
            status_text="Ошибка сканирования",
            log_message="ERROR: Strategy scan execution failed",
            support_status_code="ready_after_error",
            notification_kind="none",
            baseline_variant="stun" if scan_protocol in {"stun_voice", "udp_games"} else "tcp",
        )

    total_available = max(0, int(getattr(report, "total_available", 0) or 0))

    if report.cancelled:
        if scan_cursor > 0:
            save_resume_state(
                scan_target,
                scan_protocol,
                scan_cursor,
                scan_udp_games_scope,
            )
        else:
            clear_resume_state(
                scan_target,
                scan_protocol,
                scan_udp_games_scope,
            )
    else:
        full_scan_completed = (
            scan_mode == "full"
            and total_available > 0
            and report.total_tested >= total_available
        )
        if full_scan_completed:
            clear_resume_state(
                scan_target,
                scan_protocol,
                scan_udp_games_scope,
            )
        else:
            save_resume_state(
                scan_target,
                scan_protocol,
                report.total_tested,
                scan_udp_games_scope,
            )

    total_count = max(scan_cursor, report.total_tested)
    elapsed = report.elapsed_seconds

    if report.cancelled:
        status_text = f"Отменено. Протестировано: {total_count}, рабочих: {working} ({elapsed:.1f}s)"
    else:
        status_text = f"Готово. Протестировано: {total_count}, рабочих: {working} ({elapsed:.1f}s)"

    if report.cancelled:
        notification_kind = "none"
    elif report.baseline_accessible:
        notification_kind = "baseline_accessible"
    elif working > 0:
        notification_kind = "found"
    else:
        notification_kind = "not_found"

    return StrategyScanFinishPlan(
        total_available=total_available,
        working_count=working,
        total_count=total_count,
        cancelled=bool(report.cancelled),
        baseline_accessible=bool(report.baseline_accessible),
        status_text=status_text,
        log_message=f"\n{status_text}",
        support_status_code="ready",
        notification_kind=notification_kind,
        baseline_variant="stun" if scan_protocol in {"stun_voice", "udp_games"} else "tcp",
    )


def build_finish_notification_plan(finish_plan: StrategyScanFinishPlan, *, scan_protocol: str) -> StrategyScanNotificationPlan:
    if finish_plan.notification_kind == "baseline_accessible":
        if scan_protocol == "udp_games":
            title_default = "UDP уже доступен"
        elif finish_plan.baseline_variant == "stun":
            title_default = "STUN уже доступен"
        else:
            title_default = "Домен уже доступен"

        if finish_plan.baseline_variant == "stun":
            return StrategyScanNotificationPlan(
                kind="warning",
                title_key="page.strategy_scan.baseline_ok_title_stun",
                title_default=title_default,
                body_key="page.strategy_scan.baseline_ok_text_stun",
                body_default="STUN/UDP уже доступен без обхода DPI — результаты могут быть ложноположительными",
                body_text="",
            )

        return StrategyScanNotificationPlan(
            kind="warning",
            title_key="page.strategy_scan.baseline_ok_title",
            title_default=title_default,
            body_key="page.strategy_scan.baseline_ok_text",
            body_default="Домен доступен без обхода DPI — результаты могут быть ложноположительными",
            body_text="",
        )

    if finish_plan.notification_kind == "found":
        return StrategyScanNotificationPlan(
            kind="success",
            title_key="page.strategy_scan.found",
            title_default="Найдены рабочие стратегии",
            body_key="",
            body_default="",
            body_text=f"{finish_plan.working_count} из {finish_plan.total_count}",
        )

    if finish_plan.notification_kind == "not_found":
        return StrategyScanNotificationPlan(
            kind="warning",
            title_key="page.strategy_scan.not_found",
            title_default="Рабочих стратегий не найдено",
            body_key="page.strategy_scan.try_full",
            body_default="Попробуйте полный режим сканирования",
            body_text="",
        )

    return StrategyScanNotificationPlan(
        kind="none",
        title_key="",
        title_default="",
        body_key="",
        body_default="",
        body_text="",
    )
