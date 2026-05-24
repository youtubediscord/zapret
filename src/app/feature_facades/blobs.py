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


def build_blobs_feature() -> BlobsFeature:
    def _public():
        from blobs import public as blobs_public

        return blobs_public

    return BlobsFeature(
        get_blobs_info=lambda: _public().get_blobs_info(),
        get_bin_folder=lambda: _public().get_bin_folder(),
        save_user_blob=lambda *args, **kwargs: _public().save_user_blob(*args, **kwargs),
        delete_user_blob=lambda *args, **kwargs: _public().delete_user_blob(*args, **kwargs),
        reload_blobs=lambda: _public().reload_blobs(),
        open_bin_folder=lambda: _public().open_bin_folder(),
        open_blobs_json=lambda: _public().open_blobs_json(),
    )
