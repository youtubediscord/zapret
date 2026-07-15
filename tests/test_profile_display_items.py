from __future__ import annotations

from types import SimpleNamespace
import unittest

from profile.display_items import build_profile_display_items
from profile.list_view_state import apply_profile_folder_state_to_items


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
    order_is_manual: bool = False,
    profile_name: str = "",
):
    return SimpleNamespace(
        key=key,
        persistent_key=f"sig:{key}",
        profile_index=order,
        display_name=name,
        profile_name=profile_name,
        enabled=enabled,
        in_preset=in_preset,
        strategy_id=strategy_id,
        strategy_name="Активная" if strategy_id != "none" else "Стратегия не выбрана",
        match_lines=lines,
        list_type=list_type,
        rating="",
        favorite=False,
        group="youtube",
        group_name="YouTube",
        order=order,
        order_is_manual=order_is_manual,
    )


class ProfileDisplayItemsTests(unittest.TestCase):
    def test_hostlist_and_ipset_with_same_target_are_plain_badge_rows(self) -> None:
        rows = build_profile_display_items((
            _item(
                "hostlist-youtube",
                name="YouTube",
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

    def test_display_items_use_ready_display_name_without_rewriting(self) -> None:
        rows = build_profile_display_items((
            _item(
                "hostlist-list-youtube",
                name="TCP 80,443 • hostlist list-youtube.txt",
                list_type="hostlist",
                lines=("--filter-tcp=80,443", "--hostlist=lists/list-youtube.txt"),
                order=1,
            ),
        ))

        self.assertEqual(rows[0].display_name, "TCP 80,443 • hostlist list-youtube.txt")

    def test_display_items_do_not_resolve_social_list_names(self) -> None:
        rows = build_profile_display_items((
            _item(
                "hostlist-facebook",
                name="TCP 80,443 • hostlist facebook.txt",
                list_type="hostlist",
                lines=("--filter-tcp=80,443", "--hostlist=lists/facebook.txt"),
                in_preset=False,
            ),
            _item(
                "hostlist-instagram",
                name="TCP 80,443 • hostlist instagram.txt",
                list_type="hostlist",
                lines=("--filter-tcp=80,443", "--hostlist=lists/instagram.txt"),
                in_preset=False,
            ),
            _item(
                "hostlist-twitter",
                name="TCP 80,443 • hostlist twitter.txt",
                list_type="hostlist",
                lines=("--filter-tcp=80,443", "--hostlist=lists/twitter.txt"),
                in_preset=False,
            ),
            _item(
                "hostlist-twimg",
                name="TCP 80,443 • hostlist twimg.txt",
                list_type="hostlist",
                lines=("--filter-tcp=80,443", "--hostlist=lists/twimg.txt"),
                in_preset=False,
            ),
        ))

        names_by_key = {row.key: row.display_name for row in rows}
        self.assertEqual(names_by_key["hostlist-facebook"], "TCP 80,443 • hostlist facebook.txt")
        self.assertEqual(names_by_key["hostlist-instagram"], "TCP 80,443 • hostlist instagram.txt")
        self.assertEqual(names_by_key["hostlist-twitter"], "TCP 80,443 • hostlist twitter.txt")
        self.assertEqual(names_by_key["hostlist-twimg"], "TCP 80,443 • hostlist twimg.txt")

    def test_display_items_do_not_override_ready_name_with_profile_name(self) -> None:
        rows = build_profile_display_items((
            _item(
                "my-sites",
                name="Мои сайты",
                profile_name="Другое имя",
                list_type="ipset",
                lines=("--filter-tcp=80,443-65535", "--ipset=lists/ipset-all.txt"),
                order=1,
            ),
        ))

        self.assertEqual(rows[0].display_name, "Мои сайты")

    def test_real_preset_profile_keeps_folder_group_instead_of_current_group(self) -> None:
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
        self.assertEqual(by_key["active-youtube"].group, "youtube")
        self.assertEqual(by_key["active-youtube"].group_name, "YouTube")
        self.assertEqual(by_key["catalog-discord"].group, "youtube")

    def test_default_order_puts_tcp_profiles_before_udp_profiles(self) -> None:
        rows = apply_profile_folder_state_to_items(build_profile_display_items((
            _item(
                "udp-youtube",
                name="YouTube UDP",
                list_type="hostlist",
                lines=("--filter-udp=443", "--hostlist=lists/youtube.txt"),
                order=0,
            ),
            _item(
                "tcp-youtube",
                name="YouTube TCP",
                list_type="hostlist",
                lines=("--filter-tcp=80,443", "--hostlist=lists/youtube.txt"),
                order=1,
            ),
        )), {})

        self.assertEqual([row.key for row in rows], ["tcp-youtube", "udp-youtube"])

    def test_default_order_puts_l7_profiles_after_udp_profiles(self) -> None:
        rows = apply_profile_folder_state_to_items(build_profile_display_items((
            _item(
                "l7-discord",
                name="Discord L7",
                list_type="hostlist",
                lines=("--filter-l7=discord", "--hostlist=lists/discord.txt"),
                order=0,
            ),
            _item(
                "udp-discord",
                name="Discord UDP (обычно не нужно)",
                list_type="hostlist",
                lines=("--filter-udp=50000-59000", "--hostlist=lists/discord.txt"),
                order=1,
            ),
            _item(
                "tcp-discord",
                name="Discord TCP",
                list_type="hostlist",
                lines=("--filter-tcp=443", "--hostlist=lists/discord.txt"),
                order=2,
            ),
        )), {})

        self.assertEqual([row.key for row in rows], ["tcp-discord", "udp-discord", "l7-discord"])

    def test_manual_profile_order_wins_over_protocol_order(self) -> None:
        rows = build_profile_display_items((
            _item(
                "udp-youtube",
                name="YouTube UDP",
                list_type="hostlist",
                lines=("--filter-udp=443", "--hostlist=lists/youtube.txt"),
                order=0,
                order_is_manual=True,
            ),
            _item(
                "tcp-youtube",
                name="YouTube TCP",
                list_type="hostlist",
                lines=("--filter-tcp=80,443", "--hostlist=lists/youtube.txt"),
                order=1,
                order_is_manual=True,
            ),
        ))

        self.assertEqual([row.key for row in rows], ["udp-youtube", "tcp-youtube"])


if __name__ == "__main__":
    unittest.main()
