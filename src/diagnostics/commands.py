from __future__ import annotations

from diagnostics.worker import ConnectionTestWorker


def create_connection_test_worker(test_type: str = "all") -> ConnectionTestWorker:
    return ConnectionTestWorker(test_type)
