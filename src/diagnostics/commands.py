from __future__ import annotations

from diagnostics.worker import ConnectionTestWorker


def create_connection_test_worker(test_type: str = "all") -> ConnectionTestWorker:
    return ConnectionTestWorker(test_type)


def create_connection_support_prepare_worker(
    request_id: int,
    *,
    selection: str,
    prepare_connection_support=None,
    parent=None,
):
    from diagnostics.support_worker import ConnectionSupportPrepareWorker

    return ConnectionSupportPrepareWorker(
        request_id,
        selection=selection,
        prepare_connection_support=prepare_connection_support or globals()["prepare_connection_support"],
        parent=parent,
    )


def prepare_connection_support(*, selection: str):
    from diagnostics.page_plans import prepare_support_request_for_connection

    return prepare_support_request_for_connection(selection=selection)
