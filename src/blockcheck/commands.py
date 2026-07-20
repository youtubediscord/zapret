from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
import os

from log.log import global_logger
from log.run_log_sessions import run_log_sessions


@dataclass(slots=True)
class BlockcheckRunLogState:
    path: str | None
    created: bool


def create_blockcheck_worker(
    *,
    mode: str = "full",
    extra_domains: list[str] | None = None,
    skip_preflight_failed: bool = False,
    parent=None,
):
    from blockcheck.worker import BlockcheckWorker

    return BlockcheckWorker(
        mode=mode,
        extra_domains=extra_domains,
        skip_preflight_failed=skip_preflight_failed,
        start_run_log=start_blockcheck_run_log,
        append_run_log=append_blockcheck_run_log,
        close_run_log=close_blockcheck_run_log,
        parent=parent,
    )


def create_strategy_scan_worker(
    *,
    target: str,
    mode: str = "quick",
    start_index: int = 0,
    scan_protocol: str = "tcp_https",
    udp_games_scope: str = "all",
    shutdown_sync,
    parent=None,
):
    from blockcheck.strategy_scan_worker import StrategyScanWorker

    return StrategyScanWorker(
        target=target,
        mode=mode,
        start_index=start_index,
        scan_protocol=scan_protocol,
        udp_games_scope=udp_games_scope,
        shutdown_sync=shutdown_sync,
        start_run_log=start_strategy_scan_run_log,
        append_run_log=append_strategy_scan_run_log,
        close_run_log=close_strategy_scan_run_log,
        parent=parent,
    )


def load_page_initial_state():
    from blockcheck.page_runtime import load_page_initial_state as _load_page_initial_state

    return _load_page_initial_state()


def prepare_support(*, run_log_file: str | None, mode_label: str, extra_domains: list[str]):
    from blockcheck.page_runtime import prepare_support as _prepare_support

    return _prepare_support(
        run_log_file=run_log_file,
        mode_label=mode_label,
        extra_domains=extra_domains,
    )


def run_user_domain_action(action: str, domain: str):
    import blockcheck.page_runtime as blockcheck_page_runtime

    action_name = str(action or "").strip().lower()
    if action_name == "add":
        return blockcheck_page_runtime.add_user_domain(domain)
    if action_name == "remove":
        blockcheck_page_runtime.remove_user_domain(domain)
        return str(domain or "").strip()
    raise ValueError(f"Неизвестное действие домена BlockCheck: {action_name}")


def make_blockcheck_run_log_path(mode: str) -> str:
    from config.runtime_layout import APPLICATION_PATHS

    log_dir = str(APPLICATION_PATHS.logs_dir)
    try:
        active_log = getattr(global_logger, "log_file", None)
        if isinstance(active_log, str) and active_log.strip():
            resolved_dir = os.path.dirname(active_log)
            if resolved_dir:
                log_dir = resolved_dir
    except Exception:
        pass

    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    raw_mode = str(mode or "full").strip().lower()
    safe_mode = "".join(ch if (ch.isalnum() or ch in ("_", "-")) else "_" for ch in raw_mode) or "full"
    return os.path.join(log_dir, f"blockcheck_run_{ts}_{safe_mode}.log")


def start_blockcheck_run_log(mode: str, extra_domains: list[str]):
    path = make_blockcheck_run_log_path(mode)
    header = (
        f"=== Blockcheck Run Log ({datetime.now():%Y-%m-%d %H:%M:%S}) ===\n"
        f"Mode: {mode}\n"
        f"Extra domains: {len(extra_domains)}\n"
    )
    if extra_domains:
        header += f"Domains: {', '.join(extra_domains)}\n"
    header += "=" * 60 + "\n\n"
    created = run_log_sessions.start(path, header)
    return BlockcheckRunLogState(path=path if created else None, created=created)


def append_blockcheck_run_log(path: str | None, message: str) -> None:
    run_log_sessions.append(path, message)


def close_blockcheck_run_log(path: str | None) -> None:
    run_log_sessions.close(path)


def build_quick_target_menu_plan(*, scan_protocol: str, current_value: str):
    from blockcheck.strategy_scan_page_plans import build_quick_target_menu_plan as _build_plan

    return _build_plan(scan_protocol=scan_protocol, current_value=current_value)


def prepare_strategy_scan_support(
    *,
    run_log_file,
    target: str,
    protocol_label: str,
    mode_label: str,
    scan_protocol: str,
):
    from blockcheck.strategy_scan_logs import prepare_support

    return prepare_support(
        run_log_file=run_log_file,
        target=target,
        protocol_label=protocol_label,
        mode_label=mode_label,
        scan_protocol=scan_protocol,
    )


def start_strategy_scan_run_log(
    *,
    target: str,
    mode: str,
    scan_protocol: str,
    resume_index: int,
    udp_games_scope: str,
):
    from blockcheck.strategy_scan_logs import start_run_log

    return start_run_log(
        target=target,
        mode=mode,
        scan_protocol=scan_protocol,
        resume_index=resume_index,
        udp_games_scope=udp_games_scope,
    )


def append_strategy_scan_run_log(path: str | None, message: str) -> None:
    from blockcheck.strategy_scan_logs import append_run_log

    append_run_log(path, message)


def close_strategy_scan_run_log(path: str | None) -> None:
    run_log_sessions.close(path)
