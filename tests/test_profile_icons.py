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

    def test_vencord_profile_uses_brand_icon(self) -> None:
        icon = resolve_profile_icon(
            "vencord.dev",
            ("--filter-tcp=80,443", "--hostlist=lists/vencord.txt"),
        )

        self.assertEqual(icon.icon_name, "simple:vencord:VC")
        self.assertEqual(icon.color, "#EB7396")

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

    def test_exclusion_profile_uses_exclusion_icon(self) -> None:
        icon = resolve_profile_icon(
            "Исключения (RU сайты)",
            (
                "--filter-tcp=80,443-65535",
                "--ipset=lists/ipset-ru.txt",
                "--ipset=lists/ipset-dns.txt",
                "--ipset=lists/ipset-exclude.txt",
            ),
        )

        self.assertEqual(icon.icon_name, "fa5s.minus-circle")
        self.assertEqual(icon.color, "#FACC15")

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

    def test_hetzner_profile_uses_hoster_icon(self) -> None:
        icon = resolve_profile_icon(
            "Hetzner TCP",
            ("--filter-tcp=80,443-65535", "--ipset=lists/ipset-hetzner.txt"),
        )

        self.assertEqual(icon.icon_name, "simple:hetzner:HE")
        self.assertEqual(icon.color, "#D50C2D")

    def test_digitalocean_profile_uses_hoster_icon(self) -> None:
        icon = resolve_profile_icon(
            "DigitalOcean TCP",
            ("--filter-tcp=80,443-65535", "--ipset=lists/ipset-digitalocean.txt"),
        )

        self.assertEqual(icon.icon_name, "simple:digitalocean:DO")
        self.assertEqual(icon.color, "#0080FF")

    def test_datacamp_profile_uses_hoster_icon(self) -> None:
        icon = resolve_profile_icon(
            "Datacamp TCP",
            ("--filter-tcp=80,443-65535", "--ipset=lists/ipset-datacamp.txt"),
        )

        self.assertEqual(icon.icon_name, "fa5s.cloud")
        self.assertEqual(icon.color, "#60A5FA")

    def test_novoserve_profile_uses_hoster_icon(self) -> None:
        icon = resolve_profile_icon(
            "NovoServe TCP",
            ("--filter-tcp=80,443-65535", "--ipset=lists/ipset-novoserve.txt"),
        )

        self.assertEqual(icon.icon_name, "fa5s.server")
        self.assertEqual(icon.color, "#2563EB")

    def test_google_cloud_profile_uses_google_icon(self) -> None:
        icon = resolve_profile_icon(
            "Google Cloud TCP",
            ("--filter-tcp=80,443-65535", "--ipset=lists/ipset-usa-google.txt"),
        )

        self.assertEqual(icon.icon_name, "simple:google:GO")
        self.assertEqual(icon.color, "#4285F4")

    def test_speedtest_profile_uses_brand_icon_from_list_file(self) -> None:
        icon = resolve_profile_icon(
            "Speedtest",
            ("--filter-tcp=443,8080", "--hostlist=lists/speedtest.txt"),
        )

        self.assertEqual(icon.icon_name, "simple:speedtest:ST")

    def test_fandom_profile_uses_brand_icon_from_list_file(self) -> None:
        icon = resolve_profile_icon(
            "Fandom",
            ("--filter-tcp=443", "--hostlist=lists/fandom.txt"),
        )

        self.assertEqual(icon.icon_name, "simple:fandom:FA")
        self.assertEqual(icon.color, "#FA005A")

    def test_game_service_hostlists_use_brand_icons(self) -> None:
        cases = (
            ("EpicGames & Fortnite", "--hostlist=lists/epicgames-fortnite.txt", "simple:epicgames:EG"),
            ("Ubisoft", "--hostlist=lists/ubisoft.txt", "simple:ubisoft:UB"),
            ("Amazon TCP", "--hostlist=lists/amazon.txt", "fa5b.amazon"),
            ("cloudfront.net", "--hostlist=lists/cloudfront.txt", "fa5b.amazon"),
        )

        for display_name, list_line, expected_icon in cases:
            with self.subTest(display_name=display_name):
                icon = resolve_profile_icon(display_name, ("--filter-tcp=80,443-65535", list_line))

                self.assertEqual(icon.icon_name, expected_icon)

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

    def test_microsoft_store_profile_uses_microsoft_icon(self) -> None:
        icon = resolve_profile_icon(
            "Microsoft Store",
            ("--filter-tcp=443", "--hostlist=lists/microsoft-store.txt"),
        )

        self.assertEqual(icon.icon_name, "fa5b.microsoft")

    def test_rbxcdn_profiles_use_roblox_icon(self) -> None:
        cases = (
            ("tr.rbxcdn.com", "--hostlist=lists/tr-rbxcdn-com.txt"),
            ("css.rbxcdn.com", "--hostlist=lists/css-rbxcdn-com.txt"),
            ("js.rbxcdn.com", "--hostlist=lists/js-rbxcdn-com.txt"),
        )

        for display_name, list_line in cases:
            with self.subTest(display_name=display_name):
                icon = resolve_profile_icon(display_name, ("--filter-tcp=80,443", list_line))

                self.assertEqual(icon.icon_name, "simple:roblox:RB")
                self.assertEqual(icon.color, "#E2231A")

    def test_githubusercontent_profile_uses_github_icon(self) -> None:
        icon = resolve_profile_icon(
            "githubusercontent.com",
            ("--filter-tcp=443", "--hostlist-domains=raw.githubusercontent.com,objects.githubusercontent.com"),
        )

        self.assertEqual(icon.icon_name, "simple:github:GH")
        self.assertEqual(icon.color, "#F0F3F6")

    def test_ytimg_preview_profile_uses_youtube_icon(self) -> None:
        icon = resolve_profile_icon(
            "i.ytimg.com (превью роликов)",
            ("--filter-tcp=443", "--hostlist=lists/i-ytimg.txt"),
        )

        self.assertEqual(icon.icon_name, "simple:youtube:YT")
        self.assertEqual(icon.color, "#FF0000")


if __name__ == "__main__":
    unittest.main()
