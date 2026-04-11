from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime

from log import global_logger
from ui.support_request_actions import prepare_blockcheck_support_request


@dataclass(slots=True)
class BlockcheckRunLogState:
    path: str | None
    created: bool


class BlockcheckPageController:
    @staticmethod
    def load_user_domains() -> list[str]:
        from blockcheck.targets import load_user_domains

        return list(load_user_domains())

    @staticmethod
    def add_user_domain(text: str) -> str | None:
        from blockcheck.targets import _normalize_domain, add_user_domain

        if not add_user_domain(text):
            return None
        return _normalize_domain(text)

    @staticmethod
    def remove_user_domain(domain: str) -> None:
        from blockcheck.targets import remove_user_domain

        remove_user_domain(domain)

    @staticmethod
    def make_run_log_path(mode: str) -> str:
        from config import LOGS_FOLDER

        log_dir = LOGS_FOLDER
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

    @staticmethod
    def start_run_log(mode: str, extra_domains: list[str]) -> BlockcheckRunLogState:
        path = BlockcheckPageController.make_run_log_path(mode)
        try:
            log_dir = os.path.dirname(path)
            os.makedirs(log_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8-sig") as f:
                f.write(f"=== Blockcheck Run Log ({datetime.now():%Y-%m-%d %H:%M:%S}) ===\n")
                f.write(f"Mode: {mode}\n")
                f.write(f"Extra domains: {len(extra_domains)}\n")
                if extra_domains:
                    f.write(f"Domains: {', '.join(extra_domains)}\n")
                f.write("=" * 60 + "\n\n")
            return BlockcheckRunLogState(path=path, created=True)
        except Exception:
            return BlockcheckRunLogState(path=None, created=False)

    @staticmethod
    def append_run_log(path: str | None, message: str) -> None:
        if not path:
            return
        try:
            text = str(message or "")
            if not text.endswith("\n"):
                text += "\n"
            with open(path, "a", encoding="utf-8-sig") as f:
                f.write(text)
        except Exception:
            pass

    @staticmethod
    def prepare_support(*, run_log_file: str | None, mode_label: str, extra_domains: list[str]):
        return prepare_blockcheck_support_request(
            run_log_file=run_log_file,
            mode_label=mode_label,
            extra_domains=extra_domains,
        )
