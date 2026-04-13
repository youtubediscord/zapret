from __future__ import annotations

from ._shared import parse_source_preset


def parse(text: str):
    return parse_source_preset(text)
