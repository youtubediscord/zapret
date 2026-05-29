from __future__ import annotations

from typing import Callable


def open_url(url: str, *, open_url_fn: Callable | None = None):
    if open_url_fn is not None:
        return open_url_fn(url)

    from app.external_actions import open_url as default_open_url

    return default_open_url(url)


__all__ = ["open_url"]
