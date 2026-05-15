from __future__ import annotations

from datetime import datetime
from pathlib import Path

from config.config import LOGS_FOLDER
from support_request_actions import prepare_strategy_scan_support_request
from blockcheck.strategy_scan_resume import resume_state_path
from blockcheck.strategy_scan_state import StrategyScanRunLogState

def _sanitize_slug(value: str, fallback: str) -> str:
    raw = (value or "").strip().lower()
    cleaned = "".join(ch if (ch.isalnum() or ch in ("_", "-")) else "_" for ch in raw)
    cleaned = cleaned.strip("_")
    return cleaned or fallback


def _resolve_log_dir() -> Path:
    log_dir = Path(LOGS_FOLDER)

    try:
        from log.log import global_logger


        active_log = getattr(global_logger, "log_file", None)
        if isinstance(active_log, str) and active_log.strip():
            resolved_dir = Path(active_log).parent
            if str(resolved_dir):
                log_dir = resolved_dir
    except Exception:
        pass

    return log_dir


def make_run_log_path(
    target: str,
    mode: str,
    scan_protocol: str,
    udp_games_scope: str = "all",
) -> Path:
    ts = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    safe_mode = _sanitize_slug(mode, "mode")
    safe_protocol = _sanitize_slug(scan_protocol, "protocol")
    safe_scope = _sanitize_slug(udp_games_scope, "scope")
    safe_target = _sanitize_slug(target, "target")
    scope_suffix = f"_{safe_scope}" if scan_protocol == "udp_games" else ""
    filename = (
        f"blockcheck_run_{ts}_strategy_scan_{safe_mode}_{safe_protocol}"
        f"{scope_suffix}_{safe_target}.log"
    )
    return _resolve_log_dir() / filename


def start_run_log(
    *,
    target: str,
    mode: str,
    scan_protocol: str,
    resume_index: int,
    udp_games_scope: str = "all",
) -> StrategyScanRunLogState:
    primary_path = make_run_log_path(
        target=target,
        mode=mode,
        scan_protocol=scan_protocol,
        udp_games_scope=udp_games_scope,
    )
    candidates = [primary_path]

    tried: set[Path] = set()
    for path in candidates:
        if path in tried:
            continue
        tried.add(path)
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            with path.open("w", encoding="utf-8-sig") as f:
                f.write(f"=== Strategy Scan Run Log ({datetime.now():%Y-%m-%d %H:%M:%S}) ===\n")
                f.write(f"Mode: {mode}\n")
                f.write(f"Protocol: {scan_protocol}\n")
                if scan_protocol == "udp_games":
                    f.write(f"UDP games scope: {udp_games_scope}\n")
                f.write(f"Target: {target}\n")
                f.write(f"Resume index: {max(0, int(resume_index))}\n")
                f.write("=" * 70 + "\n\n")
            return StrategyScanRunLogState(path=path, created=True)
        except Exception:
            continue

    return StrategyScanRunLogState(path=None, created=False)


def append_run_log(path: Path | None, message: str) -> None:
    if path is None:
        return
    try:
        text = str(message or "")
        if not text.endswith("\n"):
            text += "\n"
        with path.open("a", encoding="utf-8-sig") as f:
            f.write(text)
    except Exception:
        pass


def prepare_support(
    *,
    run_log_file: Path | None,
    target: str,
    protocol_label: str,
    mode_label: str,
    scan_protocol: str,
):
    return prepare_strategy_scan_support_request(
        run_log_file=str(run_log_file) if run_log_file is not None else None,
        target=target,
        protocol_label=protocol_label,
        mode_label=mode_label,
        resume_state_path=resume_state_path(),
        scan_protocol=scan_protocol,
    )
