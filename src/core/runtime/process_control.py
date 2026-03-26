from __future__ import annotations

from pathlib import Path


def read_pid_file(path: Path) -> int | None:
    try:
        value = path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None
    except Exception:
        return None

    if not value:
        return None
    try:
        pid = int(value)
    except Exception:
        return None
    return pid if pid > 0 else None
