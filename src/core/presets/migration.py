from __future__ import annotations


def bootstrap_repository(repository, engine: str):
    return repository.list_presets(engine)
