from __future__ import annotations

import os


def get_blobs_info() -> dict:
    from blobs.service import get_blobs_info as _get_blobs_info

    return _get_blobs_info()


def save_user_blob(name: str, blob_type: str, value: str, description: str = "") -> bool:
    from blobs.service import save_user_blob as _save_user_blob

    return bool(_save_user_blob(name, blob_type, value, description))


def delete_user_blob(name: str) -> bool:
    from blobs.service import delete_user_blob as _delete_user_blob

    return bool(_delete_user_blob(name))


def reload_blobs() -> dict:
    from blobs.service import reload_blobs as _reload_blobs

    return _reload_blobs()


def open_bin_folder() -> None:
    os.startfile(get_bin_folder())


def open_blobs_json() -> None:
    from config.config import INDEXJSON_FOLDER

    os.startfile(os.path.join(INDEXJSON_FOLDER, "blobs.json"))


def get_bin_folder() -> str:
    from config.config import BIN_FOLDER

    return str(BIN_FOLDER)
