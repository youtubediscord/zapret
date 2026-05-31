from __future__ import annotations

from utils.subproc import run_hidden


def open_program_folder() -> None:
    run_hidden("explorer.exe .", shell=True)


__all__ = ["open_program_folder"]
