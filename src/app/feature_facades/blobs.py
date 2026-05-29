from __future__ import annotations

from dataclasses import dataclass
from typing import Callable


@dataclass(frozen=True, slots=True)
class BlobsFeature:
    get_blobs_info: Callable
    get_bin_folder: Callable
    save_user_blob: Callable
    delete_user_blob: Callable
    reload_blobs: Callable
    open_bin_folder: Callable
    open_blobs_json: Callable
    create_blobs_load_worker: Callable
    create_blob_action_worker: Callable
    create_blob_open_action_worker: Callable


def build_blobs_feature() -> BlobsFeature:
    def _public():
        from blobs import public as blobs_public

        return blobs_public

    def _create_blobs_load_worker(request_id: int, *, reload: bool = False, parent=None):
        from blobs.workers import BlobsLoadWorker

        return BlobsLoadWorker(
            request_id,
            reload=bool(reload),
            parent=parent,
        )

    def _create_blob_action_worker(
        request_id: int,
        *,
        action: str,
        name: str = "",
        blob_type: str = "",
        value: str = "",
        description: str = "",
        parent=None,
    ):
        from blobs.workers import BlobActionWorker

        return BlobActionWorker(
            request_id,
            action=action,
            name=name,
            blob_type=blob_type,
            value=value,
            description=description,
            parent=parent,
        )

    def _create_blob_open_action_worker(request_id: int, *, action: str, parent=None):
        from blobs.workers import BlobOpenActionWorker

        return BlobOpenActionWorker(
            request_id,
            action=action,
            parent=parent,
        )

    feature = BlobsFeature(
        get_blobs_info=lambda: _public().get_blobs_info(),
        get_bin_folder=lambda: _public().get_bin_folder(),
        save_user_blob=lambda *args, **kwargs: _public().save_user_blob(*args, **kwargs),
        delete_user_blob=lambda *args, **kwargs: _public().delete_user_blob(*args, **kwargs),
        reload_blobs=lambda: _public().reload_blobs(),
        open_bin_folder=lambda: _public().open_bin_folder(),
        open_blobs_json=lambda: _public().open_blobs_json(),
        create_blobs_load_worker=_create_blobs_load_worker,
        create_blob_action_worker=_create_blob_action_worker,
        create_blob_open_action_worker=_create_blob_open_action_worker,
    )
    return feature
