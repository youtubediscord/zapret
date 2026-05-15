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
    from blobs import public as blobs_public

    return BlobsFeature(
        get_blobs_info=blobs_public.get_blobs_info,
        get_bin_folder=blobs_public.get_bin_folder,
        save_user_blob=blobs_public.save_user_blob,
        delete_user_blob=blobs_public.delete_user_blob,
        reload_blobs=blobs_public.reload_blobs,
        open_bin_folder=blobs_public.open_bin_folder,
        open_blobs_json=blobs_public.open_blobs_json,
    )
