from __future__ import annotations

from lists.core.paths import get_lists_dir


LISTS_FOLDER = get_lists_dir()


def startup_lists_check() -> tuple[bool, bool]:
    from lists.core.layered_files import rebuild_all_layered_list_files
    from lists.hostlists_manager import startup_hostlists_check
    from lists.ipsets_manager import startup_ipsets_check

    hostlists_ok = bool(startup_hostlists_check())
    ipsets_ok = bool(startup_ipsets_check())
    rebuild_all_layered_list_files(LISTS_FOLDER)
    return hostlists_ok, ipsets_ok
