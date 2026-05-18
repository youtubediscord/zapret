from __future__ import annotations

from types import SimpleNamespace
import unittest

from profile.ui.profile_display_items import build_profile_display_items


def _item(
    key: str,
    *,
    name: str,
    list_type: str,
    lines: tuple[str, ...],
    strategy_id: str = "none",
    enabled: bool = False,
    in_preset: bool = True,
    order: int = 0,
):
    return SimpleNamespace(
        key=key,
        persistent_key=f"sig:{key}",
        profile_index=order,
        display_name=name,
        enabled=enabled,
        in_preset=in_preset,
        strategy_id=strategy_id,
        strategy_name="Активная" if strategy_id != "none" else "Отключено",
        match_lines=lines,
        list_type=list_type,
        rating="",
        favorite=False,
        group="youtube",
        order=order,
    )


class ProfileDisplayItemsTests(unittest.TestCase):
    def test_hostlist_and_ipset_with_same_target_are_plain_badge_rows(self) -> None:
        rows = build_profile_display_items((
            _item(
                "hostlist-youtube",
                name="youtube.com (Hostlist)",
                list_type="hostlist",
                lines=("--filter-tcp=80,443", "--hostlist=lists/youtube.txt"),
                strategy_id="tls",
                enabled=True,
                order=1,
            ),
            _item(
                "ipset-youtube",
                name="youtube.com (IPset)",
                list_type="ipset",
                lines=("--filter-tcp=80,443", "--ipset=lists/ipset-youtube.txt"),
                order=2,
            ),
        ))

        self.assertEqual(len(rows), 2)
        row = rows[0]
        self.assertEqual(row.display_name, "YouTube")
        self.assertEqual(row.key, "hostlist-youtube")
        self.assertEqual(row.list_type, "hostlist")
        self.assertFalse(hasattr(row, "variants"))

    def test_udp_ipset_does_not_merge_with_tcp_youtube_profile(self) -> None:
        rows = build_profile_display_items((
            _item(
                "hostlist-youtube-tcp",
                name="youtube.com (Hostlist)",
                list_type="hostlist",
                lines=("--filter-tcp=80,443", "--hostlist=lists/youtube.txt"),
                order=1,
            ),
            _item(
                "ipset-youtube-udp",
                name="youtube.com QUIC",
                list_type="ipset",
                lines=("--filter-udp=443", "--ipset=lists/ipset-youtube.txt"),
                order=2,
            ),
        ))

        self.assertEqual(len(rows), 2)

    def test_display_name_does_not_strip_non_zapret_list_prefix(self) -> None:
        rows = build_profile_display_items((
            _item(
                "hostlist-list-youtube",
                name="TCP 80,443 • hostlist list-youtube.txt",
                list_type="hostlist",
                lines=("--filter-tcp=80,443", "--hostlist=lists/list-youtube.txt"),
                order=1,
            ),
        ))

        self.assertEqual(rows[0].display_name, "list-youtube")

    def test_real_preset_profile_is_shown_in_current_group(self) -> None:
        rows = build_profile_display_items((
            _item(
                "active-youtube",
                name="youtube.com",
                list_type="hostlist",
                lines=("--filter-tcp=80,443", "--hostlist=lists/youtube.txt"),
                in_preset=True,
                enabled=True,
            ),
            _item(
                "catalog-discord",
                name="discord.com",
                list_type="hostlist",
                lines=("--filter-tcp=443", "--hostlist=lists/discord.txt"),
                in_preset=False,
            ),
        ))

        by_key = {row.key: row for row in rows}
        self.assertEqual(by_key["active-youtube"].group, "current")
        self.assertEqual(by_key["catalog-discord"].group, "youtube")


if __name__ == "__main__":
    unittest.main()
