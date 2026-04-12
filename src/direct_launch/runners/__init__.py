"""Runner-layer прямого запуска.

Ленивая обёртка, чтобы use-site'ы могли брать runner API без eager-импорта
всего стартового контура.
"""

from .constants import *  # noqa: F401,F403


def get_strategy_runner(*args, **kwargs):
    from .runner_factory import get_strategy_runner as _impl

    return _impl(*args, **kwargs)


def reset_strategy_runner(*args, **kwargs):
    from .runner_factory import reset_strategy_runner as _impl

    return _impl(*args, **kwargs)


def invalidate_strategy_runner(*args, **kwargs):
    from .runner_factory import invalidate_strategy_runner as _impl

    return _impl(*args, **kwargs)


def get_current_runner(*args, **kwargs):
    from .runner_factory import get_current_runner as _impl

    return _impl(*args, **kwargs)


def apply_all_filters(*args, **kwargs):
    from .args_filters import apply_all_filters as _impl

    return _impl(*args, **kwargs)


def build_args_with_deduped_blobs(*args, **kwargs):
    from blobs.service import build_args_with_deduped_blobs as _impl

    return _impl(*args, **kwargs)


def get_blobs_info(*args, **kwargs):
    from blobs.service import get_blobs_info as _impl

    return _impl(*args, **kwargs)


def save_user_blob(*args, **kwargs):
    from blobs.service import save_user_blob as _impl

    return _impl(*args, **kwargs)


def delete_user_blob(*args, **kwargs):
    from blobs.service import delete_user_blob as _impl

    return _impl(*args, **kwargs)


def reload_blobs(*args, **kwargs):
    from blobs.service import reload_blobs as _impl

    return _impl(*args, **kwargs)

