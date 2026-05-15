from __future__ import annotations

from collections.abc import Callable


def set_runtime_feature_status(runtime_feature, text: str) -> None:
    """Единая точка runtime для короткого UI-статуса."""
    runtime_feature.ui_port.set_status(str(text or ""))


def set_runtime_owner_status(runtime_owner, text: str) -> None:
    set_runtime_feature_status(runtime_owner._runtime_feature, text)


def runtime_status_callback(runtime_feature) -> Callable[[str], None]:
    return lambda text: set_runtime_feature_status(runtime_feature, text)


def runtime_owner_status_callback(runtime_owner) -> Callable[[str], None]:
    return lambda text: set_runtime_owner_status(runtime_owner, text)
