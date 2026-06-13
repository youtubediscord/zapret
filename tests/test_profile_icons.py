from __future__ import annotations

import unittest

from profile.icons import resolve_profile_icon


class ProfileIconTests(unittest.TestCase):
    def test_known_profile_uses_brand_icon_from_list_file(self) -> None:
        icon = resolve_profile_icon(
            "YouTube",
            ("--filter-tcp=80,443", "--hostlist=lists/youtube.txt"),
        )

        self.assertEqual(icon.icon_name, "simple:youtube:YT")
        self.assertEqual(icon.color, "#FF0000")

    def test_ipset_prefix_does_not_hide_known_identity(self) -> None:
        icon = resolve_profile_icon(
            "Discord",
            ("--filter-tcp=80,443", "--ipset=lists/ipset-discord.txt"),
        )

        self.assertEqual(icon.icon_name, "simple:discord:DI")

    def test_unknown_site_gets_stable_initials_icon(self) -> None:
        first = resolve_profile_icon(
            "example.org",
            ("--filter-tcp=443", "--hostlist-domains=example.org"),
        )
        second = resolve_profile_icon(
            "example.org",
            ("--filter-tcp=443", "--hostlist-domains=example.org"),
        )

        self.assertEqual(first, second)
        self.assertEqual(first.icon_name, "profile-initials:EX")

    def test_hoster_without_brand_icon_gets_named_fallback_color(self) -> None:
        icon = resolve_profile_icon(
            "cloudflare",
            ("--filter-tcp=80,443", "--ipset=lists/ipset-cloudflare.txt"),
        )

        self.assertEqual(icon.icon_name, "simple:cloudflare:CF")
        self.assertEqual(icon.color, "#F38020")

    def test_service_alias_uses_same_brand_icon(self) -> None:
        icon = resolve_profile_icon(
            "youtube.com (RTMPS Россия)",
            ("--filter-tcp=443", "--hostlist=lists/youtubeQ.txt"),
        )

        self.assertEqual(icon.icon_name, "simple:youtube:YT")
        self.assertEqual(icon.color, "#FF0000")

    def test_display_name_can_identify_service_when_domain_bundle_is_ambiguous(self) -> None:
        icon = resolve_profile_icon(
            "youtube.com (RTMPS Россия)",
            ("--filter-tcp=443", "--hostlist-domains=www.xvideos.com,xvideos-cdn.com"),
        )

        self.assertEqual(icon.icon_name, "simple:youtube:YT")

    def test_cloudflare_variants_use_cloudflare_icon(self) -> None:
        icon = resolve_profile_icon(
            "Cloudflare IPv6 legacy TCP",
            ("--filter-tcp=443", "--ipset=lists/cloudflare-ipset_v6.txt"),
        )

        self.assertEqual(icon.icon_name, "simple:cloudflare:CF")
        self.assertEqual(icon.color, "#F38020")

    def test_general_lists_use_meaningful_generic_icon(self) -> None:
        icon = resolve_profile_icon(
            "General list TCP",
            ("--filter-tcp=80,443", "--hostlist=lists/list-general.txt"),
        )

        self.assertEqual(icon.icon_name, "fa5s.list-ul")

    def test_blacklist_uses_blocking_icon_even_with_domain_bundle(self) -> None:
        icon = resolve_profile_icon(
            "Russia blacklist TCP wide",
            (
                "--filter-tcp=80,443",
                "--hostlist-domains=awsglobalaccelerator.com,cloudfront.net,amazon.com,amazonaws.com,awsstatic.com",
            ),
        )

        self.assertEqual(icon.icon_name, "fa5s.shield-alt")

    def test_voice_profile_uses_voice_icon_from_display_name(self) -> None:
        icon = resolve_profile_icon("Голосовые звонки/чаты", ("--filter-udp=50000-51000",))

        self.assertEqual(icon.icon_name, "fa5s.microphone")

    def test_tiktok_profile_uses_brand_icon_from_list_file(self) -> None:
        icon = resolve_profile_icon(
            "TikTok",
            ("--filter-tcp=80,443", "--hostlist=lists/tiktok.txt"),
        )

        self.assertEqual(icon.icon_name, "simple:tiktok:TT")

    def test_anydesk_profiles_use_brand_icon_from_ipset_file(self) -> None:
        tcp_icon = resolve_profile_icon(
            "AnyDesk TCP",
            ("--filter-tcp=80,443,6568", "--ipset=lists/ipset-anydesk.txt"),
        )
        udp_icon = resolve_profile_icon(
            "AnyDesk UDP",
            ("--filter-udp=443,6568,50000-51000", "--ipset=lists/ipset-anydesk.txt"),
        )

        self.assertEqual(tcp_icon.icon_name, "simple:anydesk:AD")
        self.assertEqual(udp_icon.icon_name, "simple:anydesk:AD")

    def test_speedtest_profile_uses_brand_icon_from_list_file(self) -> None:
        icon = resolve_profile_icon(
            "Speedtest",
            ("--filter-tcp=443,8080", "--hostlist=lists/speedtest.txt"),
        )

        self.assertEqual(icon.icon_name, "simple:speedtest:ST")

    def test_7tv_profile_uses_tv_icon(self) -> None:
        icon = resolve_profile_icon(
            "7tv (10tv)",
            ("--filter-tcp=80,443", "--hostlist-domains=7tv.app,7tv.io,10tv.app"),
        )

        self.assertEqual(icon.icon_name, "fa5s.tv")

    def test_my_sites_profile_uses_globe_icon(self) -> None:
        icon = resolve_profile_icon(
            "Мои сайты",
            ("--filter-tcp=80,443-65535", "--hostlist=lists/other.txt"),
        )

        self.assertEqual(icon.icon_name, "fa5s.globe")


if __name__ == "__main__":
    unittest.main()
