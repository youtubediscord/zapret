from __future__ import annotations

from ..common.source_preset_models import OutRangeSettings, SendSettings, SyndataSettings


def parse_out_range(action_lines: list[str]) -> OutRangeSettings:
    return OutRangeSettings()


def parse_send(action_lines: list[str]) -> SendSettings:
    return SendSettings()


def parse_syndata(action_lines: list[str]) -> SyndataSettings:
    return SyndataSettings()


def strip_helper_lines(action_lines: list[str]) -> list[str]:
    return [line.strip() for line in action_lines if str(line).strip()]


def compose_action_lines(strategy_args: list[str], out_range: OutRangeSettings, send: SendSettings, syndata: SyndataSettings) -> list[str]:
    _ = (out_range, send, syndata)
    return [line.strip() for line in strategy_args if str(line).strip()]
