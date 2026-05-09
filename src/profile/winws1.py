from __future__ import annotations

from .models import Winws1Strategy


def parse_winws1_strategy(lines: list[str]) -> Winws1Strategy:
    dpi_desync_lines: list[str] = []
    dup_lines: list[str] = []
    wssize_lines: list[str] = []
    ip_id_lines: list[str] = []
    other_lines: list[str] = []

    for raw in lines or []:
        line = str(raw or "").strip()
        lowered = line.lower()
        if not line:
            continue
        if lowered.startswith("--dpi-desync"):
            dpi_desync_lines.append(line)
        elif lowered.startswith("--dup"):
            dup_lines.append(line)
        elif lowered.startswith("--wssize"):
            wssize_lines.append(line)
        elif lowered.startswith("--ip-id"):
            ip_id_lines.append(line)
        else:
            other_lines.append(line)

    return Winws1Strategy(
        dpi_desync_lines=dpi_desync_lines,
        dup_lines=dup_lines,
        wssize_lines=wssize_lines,
        ip_id_lines=ip_id_lines,
        strategy_lines=[str(line or "").strip() for line in lines or [] if str(line or "").strip()],
        other_lines=other_lines,
    )
