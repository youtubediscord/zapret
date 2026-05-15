from __future__ import annotations


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
        parent=parent,
    )


def create_strategy_scan_worker(
    *,
    target: str,
    mode: str = "quick",
    start_index: int = 0,
    scan_protocol: str = "tcp_https",
    udp_games_scope: str = "all",
    runtime_feature,
    parent=None,
):
    from blockcheck.strategy_scan_worker import StrategyScanWorker

    return StrategyScanWorker(
        target=target,
        mode=mode,
        start_index=start_index,
        scan_protocol=scan_protocol,
        udp_games_scope=udp_games_scope,
        runtime_feature=runtime_feature,
        parent=parent,
    )
