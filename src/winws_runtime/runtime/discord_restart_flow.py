from __future__ import annotations

from log.log import log
from winws_runtime.runtime.status_feedback import runtime_owner_status_callback


def maybe_restart_discord_after_runtime_apply(runtime_owner, *, skip_first_start: bool) -> bool:
    """Перезапускает Discord после применения пресета, если это разрешено настройкой."""
    try:
        if skip_first_start and runtime_owner._first_runtime_apply:
            return False

        from discord.discord_restart import get_discord_restart_setting

        if not bool(get_discord_restart_setting(default=True)):
            return False

        if runtime_owner._discord_manager is None:
            from discord.discord import DiscordManager

            runtime_owner._discord_manager = DiscordManager(status_callback=runtime_owner_status_callback(runtime_owner))

        return bool(runtime_owner._discord_manager.restart_discord_if_running())
    except Exception as e:
        log(f"Discord restart check error: {e}", "DEBUG")
        return False
    finally:
        if skip_first_start:
            runtime_owner._first_runtime_apply = False
