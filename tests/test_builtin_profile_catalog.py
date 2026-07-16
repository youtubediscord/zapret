from __future__ import annotations

import ipaddress
from pathlib import Path, PureWindowsPath
from types import SimpleNamespace
import unittest

from core.paths import AppPaths
from profile.models import build_profile_logical_key
from profile.parser import parse_preset_text
from profile.service import ProfilePresetService


PUBLIC_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = PUBLIC_ROOT.parent / "private_zapretgui"
ALL_PROFILES_PATH = PRIVATE_ROOT / "resources" / "profile" / "templates" / "all_profiles.txt"
WIDE_DISCORD_TCP_FILTER = "--filter-tcp=80,443,1080,2053,2083,2087,2096,8443"
WIDE_DISCORD_PRIMARY_LINES = {
    "--hostlist=lists/discord-images.txt",
    "--hostlist=lists/discord-media.txt",
    "--hostlist=lists/discord.txt",
    "--ipset=lists/ipset-discord.txt",
}
# Default v1 намеренно вернул legacy Cloudflare ipset-профили (commit 634649d3).
ACCEPTED_LEGACY_CLOUDFLARE_TCP_PROFILES = {
    ("Default v1 (game filter).txt", "Cloudflare legacy TCP"),
    ("Default v1 (game filter).txt", "Cloudflare IPv6 legacy TCP"),
    ("Default v1 (game filter).txt", "Cloudflare alt TCP"),
}
# Default v1 намеренно направляет весь Amazon AS16509 через ipset.
ACCEPTED_IPSET_AMAZON_TCP_PROFILES = {
    ("Default v1 (game filter).txt", "Amazon TCP"),
}
ACCEPTED_WIDER_PROFILE_KEYS = {
    "winws2|hostlist=discord.txt|tcp=80,443-65535",
    "winws2|hostlist=facebook.txt|tcp=80,443-65535",
    "winws2|hostlist=instagram.txt|tcp=80,443-65535",
    "winws2|hostlist=itch.txt|tcp=80,443-65535",
    "winws2|hostlist=rutor.txt|tcp=80,443-65535",
    "winws2|hostlist=rutracker.txt|tcp=80,443-65535",
    "winws2|hostlist=soundcloud.txt|tcp=80,443-65535",
    "winws2|hostlist=twitter.txt|tcp=80,443-65535",
    "winws2|hostlist=whatsapp.txt|tcp=80,443-65535",
    "winws2|ipset=ipset-telegram.txt|tcp=80,443-65535",
}
# Узкие legacy-варианты канонов в замороженных builtin preset-ах: каталог 2026-07
# расширил канонические порты (443 -> 443-65535, 80,443 -> широкие диапазоны),
# а старые preset-ы сохраняют прежние фильтры и прежние имена ('Amazon' и т.п.).
ACCEPTED_NARROWER_PROFILE_KEYS = {
    "winws1|hostlist=discord-media.txt|tcp=80,443",
    "winws1|hostlist=discord.txt|tcp=80,443",
    "winws1|hostlist=other.txt|tcp=80,443",
    "winws1|hostlist=roblox.txt|tcp=80,443",
    "winws1|ipset=ipset-amazon.txt|tcp=1024-65535",
    "winws1|ipset=ipset-amazon.txt|tcp=80,443,8443",
    "winws1|ipset=ipset-amazon.txt|udp=1024-65535",
    "winws1|ipset=ipset-amazon.txt|udp=443",
    "winws1|ipset=ipset-cloudflare.txt|tcp=1024-65535",
    "winws1|ipset=ipset-cloudflare.txt|tcp=80,443,8443",
    "winws1|ipset=ipset-cloudflare.txt|udp=1024-65535",
    "winws1|ipset=ipset-cloudflare.txt|udp=443",
    "winws1|ipset=ipset-cloudflare1.txt|tcp=1024-65535",
    "winws1|ipset=ipset-cloudflare1.txt|tcp=80,443,8443",
    "winws1|ipset=ipset-cloudflare1.txt|udp=1024-65535",
    "winws1|ipset=ipset-cloudflare1.txt|udp=443",
    "winws1|ipset=ipset-ovh.txt|tcp=1024-65535",
    "winws1|ipset=ipset-ovh.txt|tcp=80,443,8443",
    "winws1|ipset=ipset-ovh.txt|udp=1024-65535",
    "winws1|ipset=ipset-ovh.txt|udp=443",
    "winws1|ipset=ipset-timeweb.txt|tcp=1024-65535",
    "winws1|ipset=ipset-timeweb.txt|tcp=80,443,8443",
    "winws1|ipset=ipset-timeweb.txt|udp=1024-65535",
    "winws1|ipset=ipset-timeweb.txt|udp=443",
    "winws2|hostlist=russia-blacklist.txt|tcp=80,443",
    "winws2|hostlist=tankix.txt|tcp=80,443,5050,8080",
}
RUNTIME_ONLY_PROFILE_KEYS = {
    "winws1|(none)|tcp=100-25565",
    "winws1|(none)|tcp=2000-8400",
    "winws1|(none)|tcp=443",
    "winws1|(none)|tcp=443,1024-65535",
    "winws1|(none)|tcp=443-65535",
    "winws1|(none)|tcp=4950-4955",
    "winws1|(none)|tcp=6695-6705",
    "winws1|(none)|tcp=80",
    "winws1|(none)|udp=100-25565",
    "winws1|(none)|udp=1024-65535",
    "winws1|(none)|udp=19294-19344,50000-50100",
    "winws1|(none)|udp=443",
    "winws1|(none)|udp=443-65535",
    "winws1|(none)|udp=443-9000",
    "winws1|(none)|udp=50000-50090",
    "winws1|(none)|udp=50000-50099",
    "winws1|(none)|udp=50000-50100",
    "winws1|(none)|udp=50000-59000",
    "winws1|(none)|udp=50000-65535",
    "winws1|hostlist-domains=amazon.com,amazonaws.com,awsglobalaccelerator.com,awsstatic.com,epicgames.com;hostlist-domains=xmfirmwareupdater.com|tcp=443,444-65535",
    "winws1|hostlist-domains=amazon.com,amazonaws.com,awsglobalaccelerator.com,awsstatic.com,epicgames.com|tcp=443,444-65535",
    "winws1|hostlist-domains=amazon.com,amazonaws.com,awsglobalaccelerator.com,awsstatic.com,epicgames.com|udp=443,444-65535",
    "winws1|hostlist-domains=amazon.com,amazonaws.com,awsglobalaccelerator.com,awsstatic.com|tcp=443",
    "winws1|hostlist-domains=amazon.com,amazonaws.com,awsstatic.com,epicgames.com|tcp=80",
    "winws1|hostlist-domains=cloudfront.net|tcp=80",
    "winws1|hostlist-domains=cloudfront.net|tcp=443",
    "winws1|hostlist-domains=cloudfront.net|tcp=443,444-65535",
    "winws1|hostlist-domains=cloudfront.net|udp=443,444-65535",
    "winws1|hostlist-domains=android.com,dw.com,hmvmania.com,moscowtimes.ru,onlinesim.io,proton.me,roskomsvoboda.org,rublacklist.net,rutracker.cc,z-library.sk;hostlist=faceinsta.txt|tcp=443",
    "winws1|hostlist-domains=android.com,dw.com,hmvmania.com,moscowtimes.ru,onlinesim.io,proton.me,roskomsvoboda.org,rublacklist.net,rutracker.cc,z-library.sk;hostlist=youtube.txt|tcp=443",
    "winws1|hostlist-domains=android.com,dw.com,hmvmania.com,moscowtimes.ru,onlinesim.io,proton.me,roskomsvoboda.org,rublacklist.net,z-library.sk;hostlist=faceinsta.txt|tcp=443",
    "winws1|hostlist-domains=android.com,dw.com,hmvmania.com,moscowtimes.ru,onlinesim.io,proton.me,roskomsvoboda.org,rublacklist.net,z-library.sk;hostlist=youtube.txt|tcp=443",
    "winws1|hostlist-domains=animego.online,animejoy.ru,doramy.club,getchu.com|tcp=443",
    "winws1|hostlist-domains=cloudflareclient.com,cloudflarecp.com,cloudflareok.com,cloudflareportal.com|tcp=443",
    "winws1|hostlist-domains=cloudflareclient.com,cloudflarecp.com,cloudflareok.com,cloudflareportal.com|tcp=80",
    "winws1|hostlist-domains=leagueoflegends.com,playvalorant.com,pvp.net,rdatasrv.net,rgpub.io,riotcdn.com,riotcdn.net,riotclientservices.com,riotgames.com,riotgames.es;hostlist=discord.txt|udp=443",
    "winws1|hostlist-domains=main.txrevive.com,resources.txrevive.com|tcp=80,443",
    "winws1|hostlist-domains=ntc.party;hostlist=discord.txt|tcp=443",
    "winws1|hostlist-domains=ntc.party;hostlist=russia-discord.txt|tcp=443",
    "winws1|hostlist-domains=rutracker.cc,rutracker.org;ipset=ipset-all.txt|tcp=80",
    "winws1|hostlist-domains=rutracker.cc;ipset=ipset-all.txt|tcp=80",
    "winws1|hostlist-domains=rutracker.org|tcp=443",
    "winws1|hostlist-domains=www.xvideos.com,xvideos-cdn.com;hostlist=discord.txt|tcp=443",
    "winws1|hostlist-domains=www.xvideos.com,xvideos-cdn.com;hostlist=facebook.txt|tcp=443",
    "winws1|hostlist-domains=www.xvideos.com,xvideos-cdn.com;hostlist=googlevideo.txt|tcp=443",
    "winws1|hostlist-domains=www.xvideos.com,xvideos-cdn.com;hostlist=instagram.txt|tcp=443",
    "winws1|hostlist-domains=www.xvideos.com,xvideos-cdn.com;hostlist=itch.txt|tcp=443",
    "winws1|hostlist-domains=www.xvideos.com,xvideos-cdn.com;hostlist=other.txt|tcp=443",
    "winws1|hostlist-domains=www.xvideos.com,xvideos-cdn.com;hostlist=roblox.txt|tcp=443",
    "winws1|hostlist-domains=www.xvideos.com,xvideos-cdn.com;hostlist=rutor.txt|tcp=443",
    "winws1|hostlist-domains=www.xvideos.com,xvideos-cdn.com;hostlist=rutracker.txt|tcp=443",
    "winws1|hostlist-domains=www.xvideos.com,xvideos-cdn.com;hostlist=soundcloud.txt|tcp=443",
    "winws1|hostlist-domains=www.xvideos.com,xvideos-cdn.com;hostlist=twitter.txt|tcp=443",
    "winws1|hostlist-domains=www.xvideos.com,xvideos-cdn.com;hostlist=whatsapp.txt|tcp=443",
    "winws1|hostlist-domains=www.xvideos.com,xvideos-cdn.com;hostlist=youtube.txt|tcp=443",
    "winws1|hostlist-domains=xnxx.com,xvideos.com;hostlist=youtube.txt|tcp=443",
    "winws1|hostlist-domains=youtube.com|tcp=443",
    "winws1|hostlist-exclude-domains=cdn.ampproject.org,cvetovod.by,gitflic.ru,habr.com,ixbt.com,lmarena.ai,podviliepitomnik.ru,rootsplants.co.uk,searchengines.guru,st.top100.ru,use.fontawesome.com,veresk.by,xn--p1ai|tcp=443",
    "winws1|hostlist-exclude=list-exclude.txt;ipset-exclude=ipset-exclude.txt|udp=443",
    "winws1|hostlist-exclude=list-exclude.txt|tcp=80,443",
    "winws1|hostlist-exclude=list-exclude.txt|tcp=80,443,444-65535",
    "winws1|hostlist-exclude=list-exclude.txt|udp=443",
    "winws1|hostlist=discord-updates.txt,stable.dl2.discordapp.net,animego.online,animejoy.ru,rutracker.org,static.rutracker.cc,pixiv.net,cdn77.com|tcp=443",
    "winws1|hostlist=discord.txt|udp=443",
    "winws1|hostlist=facebook.txt|udp=443",
    "winws1|hostlist=faceinsta.txt|tcp=443",
    "winws1|hostlist=googlevideo.txt;ipset-ip=xxx.xxx.xxx.xxx/xx,xxx.xxx.xxx.xxx/xx|tcp=80,443",
    "winws1|hostlist=instagram.txt|udp=443",
    "winws1|hostlist=ipset-all.txt|tcp=443",
    "winws1|hostlist=itch.txt|udp=443",
    "winws1|hostlist=list-general.txt|udp=443",
    "winws1|hostlist=list-google.txt|tcp=443",
    "winws1|hostlist=mycdnlist.txt|tcp=443",
    "winws1|hostlist=mycdnlist.txt|tcp=80",
    "winws1|hostlist=mycdnlist.txt|tcp=80,443",
    "winws1|hostlist=myhostlist.txt|tcp=443",
    "winws1|hostlist=myhostlist.txt|tcp=80",
    "winws1|hostlist=other.txt|udp=443",
    "winws1|hostlist=roblox.txt|udp=443",
    "winws1|hostlist=russia-youtubeq.txt|udp=443",
    "winws1|hostlist=rutor.txt|udp=443",
    "winws1|hostlist=rutracker.txt|udp=443",
    "winws1|hostlist=soundcloud.txt|udp=443",
    "winws1|hostlist=twitter.txt|udp=443",
    "winws1|hostlist=whatsapp.txt|udp=443",
    "winws1|hostlist=youtube.txt|udp=443",
    "winws1|hostlist=youtube_v2.txt|tcp=443",
    "winws1|hostlist=youtubegv.txt|tcp=443",
    "winws1|hostlist=youtubeq.txt|udp=443",
    "winws1|ipset-exclude=ipset-exclude.txt|tcp=80,443",
    "winws1|ipset-exclude=ipset-exclude.txt|tcp=80,443,444-65535",
    "winws1|ipset-exclude=ipset-exclude.txt|udp=443",
    "winws1|ipset-exclude=ipset-exclude.txt|udp=444-65535",
    "winws1|ipset-exclude=ipset-dns.txt;ipset-exclude=ipset-exclude.txt;ipset-exclude=ipset-ru.txt|tcp=80",
    "winws1|ipset-exclude=ipset-dns.txt;ipset-exclude=ipset-exclude.txt;ipset-exclude=ipset-ru.txt|tcp=443",
    "winws1|hostlist-auto=autohostlist.txt;ipset-exclude=ipset-dns.txt;ipset-exclude=ipset-exclude.txt;ipset-exclude=ipset-ru.txt|tcp=80",
    "winws1|hostlist-auto=autohostlist.txt;ipset-exclude=ipset-dns.txt;ipset-exclude=ipset-exclude.txt;ipset-exclude=ipset-ru.txt|tcp=443",
    "winws1|ipset=ipset-all.txt|udp=443-65535",
    "winws1|ipset-exclude=ipset-dns.txt;ipset-exclude=ipset-exclude.txt;ipset-exclude=ipset-ru.txt|udp=443-65535",
    "winws1|ipset-ip=188.114.96.0/22|udp=8886",
    # Legacy-блоки, осиротевшие после реструктуризации all_profiles.txt 2026-07
    # (youtube.txt перешёл на ipset-youtube.txt, ntcparty/porn/tankix выпали из каталога):
    "winws1|(none)|l7=discord,stun;udp=19294-19344,50000-50100",
    "winws1|hostlist-domains=discord.media|tcp=2053,2083,2087,2096,8443",
    "winws1|hostlist=discord-media.txt|udp=443",
    "winws1|hostlist=discord.txt;hostlist=ntcparty.txt|tcp=443",
    "winws1|hostlist=discord.txt;hostlist=riot-valorant.txt|udp=443",
    "winws1|hostlist=ntcparty.txt;hostlist=russia-discord.txt|tcp=443",
    "winws1|hostlist=youtube.txt|tcp=80,443",
    "winws1|ipset-exclude=ipset-exclude.txt|tcp=80,443,2053,2083,2087,2096,8443",
    "winws2|hostlist=ntcparty.txt|tcp=80,443",
    "winws2|hostlist=porn.txt|tcp=80,443",
    "winws2|hostlist=riot-valorant.txt|udp=5000-5500,7000-8000",
    "winws2|hostlist=tankix.txt|udp=443-65535",
    "winws2|hostlist=youtube.txt|tcp=80,443",
    "winws2|ipset=russia-youtube-rtmps.txt|tcp=80,443-65535",
}


class BuiltinProfileCatalogTests(unittest.TestCase):
    def test_service_hostlist_profiles_use_requested_domain_lists(self) -> None:
        preset = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        expected_profiles = {
            "Cloudflare TCP": ("--filter-tcp=80,443-65535", "--hostlist=lists/cloudflare.txt"),
            "cloudfront.net": ("--filter-tcp=80,443-65535", "--hostlist=lists/cloudfront.txt"),
            "EpicGames & Fortnite": ("--filter-tcp=80,443-65535", "--hostlist=lists/epicgames-fortnite.txt"),
            "Ubisoft": ("--filter-tcp=80,443-65535", "--hostlist=lists/ubisoft.txt"),
            "Amazon TCP": ("--filter-tcp=80,443-65535", "--hostlist=lists/amazon.txt"),
            "Riot / Valorant TCP": ("--filter-tcp=443", "--hostlist=lists/riot-valorant.txt"),
        }

        for name, match_lines in expected_profiles.items():
            with self.subTest(profile=name):
                profile = _find_profile(preset.profiles, name, match_lines)
                self.assertIsNotNone(profile)
                self.assertEqual(profile.strategy.strategy_lines, [])
                self.assertEqual(profile.strategy.other_lines, [])

        expected_lists = {
            "cloudflare.txt": [
                "cloudflare-ech.com",
                "cloudflare.com",
                "cloudflareportal.com",
                "cloudflareok.com",
                "cloudflareclient.com",
                "cloudflarecp.com",
                "cloudflareinsights.com",
            ],
            "cloudfront.txt": ["cloudfront.net"],
            "epicgames-fortnite.txt": ["epicgames.com", "fortnite.com", "akamaized.net", "unrealengine.com"],
            "ubisoft.txt": ["ubi.com", "ubisoft.com", "ubisoftconnect.com", "ubisoftclub.com", "uplay.com"],
            "amazon.txt": ["amazonaws.com", "amazon.com", "awsapps.com", "awsstatic.com"],
            "riot-valorant.txt": [
                "riotgames.com",
                "riotgames.es",
                "rgpub.io",
                "rdatasrv.net",
                "valorant.com",
                "riotcdn.net",
                "riotcdn.com",
                "playvalorant.com",
                "pvp.net",
                "RiotClientServices.com",
                "LeagueofLegends.com",
            ],
        }
        lists_root = PRIVATE_ROOT / "dist" / "lists"

        for file_name, domains in expected_lists.items():
            with self.subTest(list=file_name):
                actual = (lists_root / file_name).read_text(encoding="utf-8").splitlines()
                self.assertEqual(actual, domains)

    def test_amazon_as16509_ranges_are_shipped_and_default_v1_uses_ipset(self) -> None:
        expected_profile_keys = {
            "winws2|ipset=ipset-amazon.txt|tcp=80,443-65535",
            "winws2|ipset=ipset-amazon.txt|udp=443-65535",
        }
        all_profiles = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        catalog_profiles = [
            profile
            for profile in all_profiles.profiles
            if profile.match.ipset_lines == ["--ipset=lists/ipset-amazon.txt"]
        ]
        self.assertEqual(len(catalog_profiles), 2)
        self.assertEqual(
            {_profile_catalog_key("winws2", profile) for profile in catalog_profiles},
            expected_profile_keys,
        )

        preset_path = PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2" / "Default v1 (game filter).txt"
        preset = parse_preset_text(
            preset_path.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=preset_path.name,
        )
        amazon_profiles = [
            profile
            for profile in preset.profiles
            if str(profile.name or "").strip() in {"Amazon TCP", "Amazon UDP"}
        ]
        self.assertEqual(len(amazon_profiles), 2)
        self.assertEqual(
            {_profile_catalog_key("winws2", profile) for profile in amazon_profiles},
            expected_profile_keys,
        )
        amazon_tcp = next(
            profile for profile in amazon_profiles if str(profile.name or "").strip() == "Amazon TCP"
        )
        self.assertEqual(amazon_tcp.match.hostlist_lines, [])
        self.assertEqual(amazon_tcp.match.ipset_lines, ["--ipset=lists/ipset-amazon.txt"])
        self.assertEqual(
            amazon_tcp.strategy.strategy_lines,
            [
                "--out-range=-d10",
                "--payload=tls_client_hello",
                "--lua-desync=fake:blob=tls_google:repeats=6:tcp_ts=-600000",
                "--lua-desync=fakedsplit:pattern=0x00:repeats=6:tcp_ts=-600000",
            ],
        )

        ipset_path = PRIVATE_ROOT / "dist" / "lists" / "ipset-amazon.txt"
        ipset_lines = ipset_path.read_text(encoding="utf-8").splitlines()
        self.assertEqual(ipset_lines[0], "# https://ipinfo.io/AS16509")
        entries = [line.strip() for line in ipset_lines if line.strip() and not line.lstrip().startswith("#")]
        self.assertEqual(len(entries), 7317)
        self.assertEqual(len(entries), len(set(entries)))
        self.assertTrue(
            {
                "3.0.0.0/10",
                "184.192.0.0/10",
                "2406:da00::/24",
                "2600:1f20:c000::/36",
            }.issubset(entries)
        )
        for entry in entries:
            with self.subTest(entry=entry):
                ipaddress.ip_network(entry, strict=False)

    def test_winws2_service_tcp_profiles_use_hostlists_in_builtin_presets(self) -> None:
        expected_hostlists = {
            "Amazon TCP": "--hostlist=lists/amazon.txt",
            "Cloudflare TCP": "--hostlist=lists/cloudflare.txt",
            "EpicGames & Fortnite": "--hostlist=lists/epicgames-fortnite.txt",
            "Ubisoft": "--hostlist=lists/ubisoft.txt",
        }
        offenders: list[str] = []

        for path in sorted((PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2").glob("*.txt")):
            preset = parse_preset_text(
                path.read_text(encoding="utf-8", errors="replace"),
                engine="winws2",
                source_name=path.name,
            )
            has_amazon_tcp = False
            has_epicgames = False
            cloudflare_tcp_profiles = 0

            for profile in preset.profiles:
                if not profile.enabled:
                    continue
                name = str(profile.name or "").strip()
                is_tcp_service = name in expected_hostlists or name.startswith("Cloudflare") and "TCP" in name
                if not is_tcp_service:
                    continue
                if name == "Amazon TCP":
                    has_amazon_tcp = True
                    if (path.name, name) in ACCEPTED_IPSET_AMAZON_TCP_PROFILES:
                        if profile.match.filter_lines != ["--filter-tcp=80,443-65535"]:
                            offenders.append(f"{path.name} profile {profile.index}: {name}: неправильный TCP filter")
                        if profile.match.hostlist_lines:
                            offenders.append(f"{path.name} profile {profile.index}: {name}: остался hostlist")
                        if profile.match.ipset_lines != ["--ipset=lists/ipset-amazon.txt"]:
                            offenders.append(f"{path.name} profile {profile.index}: {name}: нет Amazon ipset")
                        continue
                if name == "EpicGames & Fortnite":
                    has_epicgames = True
                if name.startswith("Cloudflare") and "TCP" in name:
                    if (path.name, name) in ACCEPTED_LEGACY_CLOUDFLARE_TCP_PROFILES:
                        continue
                    cloudflare_tcp_profiles += 1
                    if name != "Cloudflare TCP":
                        offenders.append(f"{path.name} profile {profile.index}: старый Cloudflare TCP variant {name!r}")
                        continue
                expected_hostlist = expected_hostlists.get(name)
                if expected_hostlist is None:
                    continue
                if profile.match.filter_lines != ["--filter-tcp=80,443-65535"]:
                    offenders.append(f"{path.name} profile {profile.index}: {name}: неправильный TCP filter")
                if profile.match.hostlist_lines != [expected_hostlist]:
                    offenders.append(f"{path.name} profile {profile.index}: {name}: нет {expected_hostlist}")
                if profile.match.ipset_lines:
                    offenders.append(f"{path.name} profile {profile.index}: {name}: TCP ещё использует ipset")

            if has_amazon_tcp and not has_epicgames:
                offenders.append(f"{path.name}: рядом с Amazon TCP нет EpicGames & Fortnite")
            if cloudflare_tcp_profiles > 1:
                offenders.append(f"{path.name}: несколько Cloudflare TCP profile-ов вместо одного")

        self.assertEqual(offenders, [])

    def test_winws2_cloudfront_has_separate_profile_where_cloudflare_hostlist_is_used(self) -> None:
        offenders: list[str] = []

        for path in sorted((PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2").glob("*.txt")):
            preset = parse_preset_text(
                path.read_text(encoding="utf-8", errors="replace"),
                engine="winws2",
                source_name=path.name,
            )
            uses_cloudflare_hostlist = any(
                profile.enabled
                and str(profile.name or "").strip() == "Cloudflare TCP"
                and profile.match.hostlist_lines == ["--hostlist=lists/cloudflare.txt"]
                for profile in preset.profiles
            )
            if not uses_cloudflare_hostlist:
                continue
            has_cloudfront = any(
                profile.enabled
                and str(profile.name or "").strip() == "cloudfront.net"
                and profile.match.filter_lines == ["--filter-tcp=80,443-65535"]
                and profile.match.hostlist_lines == ["--hostlist=lists/cloudfront.txt"]
                for profile in preset.profiles
            )
            if not has_cloudfront:
                offenders.append(f"{path.name}: рядом с Cloudflare TCP нет отдельного cloudfront.net")

        self.assertEqual(offenders, [])

    def test_githubusercontent_has_own_hostlist_file(self) -> None:
        github_hosts = [
            line.strip()
            for line in (PRIVATE_ROOT / "dist" / "lists" / "github.txt").read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        githubusercontent_hosts = [
            line.strip()
            for line in (PRIVATE_ROOT / "dist" / "lists" / "githubusercontent.txt")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]

        self.assertNotIn("githubusercontent.com", github_hosts)
        self.assertEqual(githubusercontent_hosts, ["githubusercontent.com"])

    def test_winws2_githubusercontent_has_separate_profile_where_github_hostlist_is_used(self) -> None:
        offenders: list[str] = []
        seen_github_presets = 0

        for path in sorted((PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2").glob("*.txt")):
            preset = parse_preset_text(
                path.read_text(encoding="utf-8", errors="replace"),
                engine="winws2",
                source_name=path.name,
            )
            uses_github_hostlist = any(
                profile.enabled
                and str(profile.name or "").strip() == "GitHub"
                and profile.match.hostlist_lines == ["--hostlist=lists/github.txt"]
                for profile in preset.profiles
            )
            if not uses_github_hostlist:
                continue
            seen_github_presets += 1
            has_githubusercontent = any(
                profile.enabled
                and str(profile.name or "").strip() == "githubusercontent.com"
                and profile.match.filter_lines == ["--filter-tcp=443"]
                and profile.match.hostlist_lines == ["--hostlist=lists/githubusercontent.txt"]
                for profile in preset.profiles
            )
            if not has_githubusercontent:
                offenders.append(f"{path.name}: рядом с GitHub нет отдельного githubusercontent.com")

        self.assertGreater(seen_github_presets, 0)
        self.assertEqual(offenders, [])

    def test_cloudfront_builtin_preset_changes_bump_metadata_versions(self) -> None:
        offenders: list[str] = []
        minimum_versions = {
            "winws1": (1, 2),
            "winws2": (2, 24),
        }

        for engine, marker in {
            "winws1": "--comment=cloudfront.net",
            "winws2": "--name=cloudfront.net",
        }.items():
            for path in sorted((PUBLIC_ROOT / "src" / "presets" / "builtin" / engine).glob("*.txt")):
                text = path.read_text(encoding="utf-8", errors="replace")
                if marker not in text:
                    continue
                header_lines = text.splitlines()[:5]
                version_line = next(
                    (line for line in header_lines if line.startswith("# BuiltinVersion: ")),
                    "",
                )
                try:
                    actual_version = tuple(
                        int(part)
                        for part in version_line.removeprefix("# BuiltinVersion: ").split(".")
                    )
                except ValueError:
                    actual_version = ()
                if actual_version < minimum_versions[engine]:
                    expected = ".".join(str(part) for part in minimum_versions[engine])
                    offenders.append(f"{engine}/{path.name}: BuiltinVersion ниже {expected}")

        self.assertEqual(offenders, [])

    def test_winws2_riot_valorant_profiles_use_hostlist_file_in_builtin_presets(self) -> None:
        offenders: list[str] = []
        seen_tcp_profiles = 0

        for path in sorted((PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2").glob("*.txt")):
            preset = parse_preset_text(
                path.read_text(encoding="utf-8", errors="replace"),
                engine="winws2",
                source_name=path.name,
            )
            for profile in preset.profiles:
                name = str(profile.name or "").strip()
                if name not in {"Riot / Valorant TCP", "Riot / Valorant UDP"}:
                    continue
                if profile.match.hostlist_domains_lines:
                    offenders.append(f"{path.name} profile {profile.index}: {name} ещё использует inline domains")
                if name != "Riot / Valorant TCP":
                    continue
                seen_tcp_profiles += 1
                if profile.match.hostlist_lines != ["--hostlist=lists/riot-valorant.txt"]:
                    offenders.append(f"{path.name} profile {profile.index}: Riot / Valorant TCP без hostlist файла")

        self.assertGreater(seen_tcp_profiles, 0)
        self.assertEqual(offenders, [])

    def test_builtin_profile_files_keep_new_separator_on_own_spaced_line(self) -> None:
        offenders: list[str] = []
        paths = [
            ALL_PROFILES_PATH,
            *sorted((PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws1").glob("*.txt")),
            *sorted((PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2").glob("*.txt")),
        ]

        for path in paths:
            lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
            for index, line in enumerate(lines):
                if line.strip().lower() != "--new":
                    continue
                previous_line = lines[index - 1] if index > 0 else ""
                previous_previous_line = lines[index - 2] if index > 1 else ""
                next_line = lines[index + 1] if index + 1 < len(lines) else ""
                next_next_line = lines[index + 2] if index + 2 < len(lines) else ""
                if (
                    previous_line.strip()
                    or next_line.strip()
                    or (index > 1 and not previous_previous_line.strip())
                    or (index + 2 < len(lines) and not next_next_line.strip())
                ):
                    offenders.append(f"{path.name}:{index + 1}")

        self.assertEqual(offenders, [])

    def test_real_default_v5_profile_list_recognizes_discord_profiles_from_catalog(self) -> None:
        preset_path = PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2" / "Default v5 (game filter).txt"
        service = ProfilePresetService(
            SimpleNamespace(
                _presets_feature=_SelectedPresetStore(preset_path),
                _app_paths=AppPaths(user_root=PRIVATE_ROOT / "resources", local_root=PRIVATE_ROOT / "resources"),
            ),
            "zapret2_mode",
        )

        payload = service.list_profiles()

        discord_updates = _items_with_match_line(payload.items, "--hostlist=lists/discord-updates.txt")
        discord_media = _items_with_match_line(payload.items, "--hostlist=lists/discord-media.txt")
        self.assertTrue(discord_updates, "Default v5 должен распознать Discord Updates как profile из preset-а")
        self.assertTrue(discord_media, "Default v5 должен распознать discord.media как profile из preset-а")
        self.assertTrue(all(item.in_preset for item in discord_updates))
        self.assertTrue(all(item.in_preset for item in discord_media))

    def test_vencord_profile_uses_dedicated_hostlist(self) -> None:
        preset = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        profiles = [profile for profile in preset.profiles if str(profile.name or "").strip() == "vencord.dev"]

        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].match.filter_lines, ["--filter-tcp=80,443"])
        self.assertEqual(profiles[0].match.hostlist_lines, ["--hostlist=lists/vencord.txt"])

        vencord_entries = _list_entries(PRIVATE_ROOT / "dist" / "lists" / "vencord.txt")
        discord_entries = _list_entries(PRIVATE_ROOT / "dist" / "lists" / "discord.txt")
        self.assertEqual(vencord_entries, ["vencord.dev"])
        self.assertNotIn("vencord.dev", discord_entries)

    def test_chatgpt_profile_uses_shipped_hostlist(self) -> None:
        preset = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        profiles = [profile for profile in preset.profiles if str(profile.name or "").strip() == "chatgpt"]

        self.assertEqual(len(profiles), 1)
        self.assertEqual(profiles[0].match.filter_lines, ["--filter-tcp=80-65535"])
        self.assertEqual(profiles[0].match.hostlist_lines, ["--hostlist=lists/chatgpt.txt"])
        self.assertEqual(
            _list_entries(PRIVATE_ROOT / "dist" / "lists" / "chatgpt.txt"),
            ["chatgpt.com", "openai.com", "oaiusercontent.com"],
        )

    def test_builtin_presets_do_not_repeat_enabled_logical_profile_matches(self) -> None:
        offenders: list[str] = []

        for engine in ("winws1", "winws2"):
            for path in sorted((PUBLIC_ROOT / "src" / "presets" / "builtin" / engine).glob("*.txt")):
                preset = parse_preset_text(
                    path.read_text(encoding="utf-8", errors="replace"),
                    engine=engine,
                    source_name=path.name,
                )
                seen: dict[str, int] = {}
                for profile in preset.profiles:
                    if not profile.enabled:
                        continue
                    logical_key = build_profile_logical_key(profile.match_signature)
                    if not logical_key:
                        continue
                    previous_index = seen.get(logical_key)
                    if previous_index is not None:
                        offenders.append(
                            f"{engine}/{path.name}: profile {previous_index} и profile {profile.index}: {logical_key}"
                        )
                        continue
                    seen[logical_key] = profile.index

        self.assertEqual(offenders, [])

    def test_all_profiles_variants_with_same_logical_match_use_same_name(self) -> None:
        preset = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        names_by_key: dict[str, set[str]] = {}

        for profile in preset.profiles:
            logical_key = build_profile_logical_key(profile.match_signature)
            clean_name = str(profile.name or "").strip()
            if logical_key and clean_name:
                names_by_key.setdefault(logical_key, set()).add(clean_name)

        offenders = {
            key: sorted(names)
            for key, names in names_by_key.items()
            if len(names) > 1
        }
        self.assertEqual(offenders, {})

    def test_winws2_builtin_discord_profiles_use_catalog_names(self) -> None:
        expected_names = _all_profile_names_by_key(
            {
                "updates.discord.com",
                "discord.media",
                "discord.com",
                "Discord UDP (обычно не нужно)",
                "Голосовые звонки/чаты",
            }
        )
        offenders: list[str] = []

        for path in sorted((PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2").glob("*.txt")):
            preset = parse_preset_text(
                path.read_text(encoding="utf-8", errors="replace"),
                engine="winws2",
                source_name=path.name,
            )
            for profile in preset.profiles:
                logical_key = build_profile_logical_key(profile.match_signature)
                expected_name = expected_names.get(logical_key)
                if expected_name and str(profile.name or "").strip() != expected_name:
                    offenders.append(
                        f"winws2/{path.name} profile {profile.index}: "
                        f"{profile.name!r} != {expected_name!r}"
                    )

        self.assertEqual(offenders, [])

    def test_winws1_builtin_profiles_use_all_profiles_names_when_available(self) -> None:
        names_by_key = _all_profile_unique_names_by_key()
        offenders: list[str] = []

        for path in sorted((PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws1").glob("*.txt")):
            preset = parse_preset_text(
                path.read_text(encoding="utf-8", errors="replace"),
                engine="winws1",
                source_name=path.name,
            )
            for profile in preset.profiles:
                logical_key = build_profile_logical_key(profile.match_signature)
                expected_name = names_by_key.get(logical_key)
                if expected_name and str(profile.name or "").strip() != expected_name:
                    offenders.append(
                        f"winws1/{path.name} profile {profile.index}: "
                        f"{profile.name!r} != {expected_name!r}"
                    )

        self.assertEqual(offenders, [])

    def test_all_profiles_and_winws2_builtin_presets_do_not_use_udp_port_80(self) -> None:
        offenders: list[str] = []

        all_profiles = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        for profile in all_profiles.profiles:
            if _profile_has_udp_port_80(profile):
                offenders.append(f"all_profiles profile {profile.index}: {profile.name}")

        for path in sorted((PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2").glob("*.txt")):
            preset = parse_preset_text(
                path.read_text(encoding="utf-8", errors="replace"),
                engine="winws2",
                source_name=path.name,
            )
            for profile in preset.profiles:
                if _profile_has_udp_port_80(profile):
                    offenders.append(f"winws2/{path.name} profile {profile.index}: {profile.display_name}")

        self.assertEqual(offenders, [])

    def test_winws2_builtin_all_sites_exclusions_keep_udp_pair_without_port_80(self) -> None:
        service_excludes = {
            "--ipset-exclude=lists/ipset-ru.txt",
            "--ipset-exclude=lists/ipset-dns.txt",
            "--ipset-exclude=lists/ipset-exclude.txt",
        }
        offenders: list[str] = []

        for path in sorted((PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2").glob("*.txt")):
            preset = parse_preset_text(
                path.read_text(encoding="utf-8", errors="replace"),
                engine="winws2",
                source_name=path.name,
            )
            has_tcp_exclusion = False
            udp_exclusions = []
            for profile in preset.profiles:
                lines = set(profile.match.all_lines())
                if not service_excludes.issubset(lines):
                    continue
                clean_name = str(profile.name or "").strip()
                if clean_name == "Все сайты (айпи)" and any(line.startswith("--filter-tcp=") for line in lines):
                    has_tcp_exclusion = True
                if clean_name != "Все сайты UDP (айпи)":
                    continue
                udp_exclusions.append(profile)
                udp_filters = sorted(line for line in lines if line.startswith("--filter-udp="))
                if udp_filters != ["--filter-udp=443-65535"]:
                    offenders.append(f"winws2/{path.name} profile {profile.index}: {udp_filters}")
                primary_lines = (
                    profile.match.hostlist_lines
                    + profile.match.hostlist_domains_lines
                    + profile.match.ipset_lines
                    + profile.match.inline_ipset_lines
                )
                if primary_lines:
                    offenders.append(f"winws2/{path.name} profile {profile.index}: has primary list {primary_lines}")

            if has_tcp_exclusion and len(udp_exclusions) != 1:
                offenders.append(f"winws2/{path.name}: expected one UDP exclusion, got {len(udp_exclusions)}")

        self.assertEqual(offenders, [])

    def test_all_profiles_keeps_wide_discord_tcp_filter_only_for_discord_entries(self) -> None:
        preset = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )

        offenders: list[str] = []
        for profile in preset.profiles:
            if WIDE_DISCORD_TCP_FILTER not in profile.match.filter_lines:
                continue
            primary_lines = set(profile.match.hostlist_lines + profile.match.ipset_lines + profile.match.hostlist_domains_lines)
            if primary_lines != {next(iter(primary_lines & WIDE_DISCORD_PRIMARY_LINES), "")}:
                offenders.append(f"{profile.display_name}: {sorted(primary_lines)}")

        self.assertEqual(offenders, [])

    def test_hetzner_profiles_have_shipped_ipset(self) -> None:
        preset = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        expected_keys = {
            "winws2|ipset=ipset-hetzner.txt|tcp=80,443-65535",
            "winws2|ipset=ipset-hetzner.txt|udp=443-65535",
        }
        actual_keys = {
            _profile_catalog_key("winws2", profile)
            for profile in preset.profiles
            if str(profile.name or "").startswith("Hetzner ")
        }

        self.assertEqual(actual_keys, expected_keys)

        list_path = PRIVATE_ROOT / "dist" / "lists" / "ipset-hetzner.txt"
        entries = [
            line.strip()
            for line in list_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(len(entries), 86)
        for entry in entries:
            ipaddress.ip_network(entry, strict=False)

    def test_cloudflare_profiles_have_shipped_ipset(self) -> None:
        preset = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        expected_keys = {
            "winws2|ipset=ipset-cloudflare.txt|tcp=80,443-65535",
            "winws2|ipset=ipset-cloudflare.txt|udp=443-65535",
        }
        actual_keys = {
            _profile_catalog_key("winws2", profile)
            for profile in preset.profiles
            if profile.match.ipset_lines == ["--ipset=lists/ipset-cloudflare.txt"]
        }

        self.assertEqual(actual_keys, expected_keys)

        list_path = PRIVATE_ROOT / "dist" / "lists" / "ipset-cloudflare.txt"
        entries = [
            line.strip()
            for line in list_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        supplied_ranges = {
            "152.114.0.0/17",
            "150.48.128.0/18",
            "152.114.128.0/18",
            "204.195.192.0/18",
            "104.18.32.0/19",
            *(f"104.21.{octet}.0/19" for octet in (0, 32, 64, 96, 192)),
            "162.159.128.0/19",
            "172.65.0.0/19",
            "172.65.32.0/19",
            *(f"104.16.{octet}.0/20" for octet in range(0, 256, 16)),
            *(f"104.17.{octet}.0/20" for octet in range(0, 256, 16)),
            *(
                f"104.18.{octet}.0/20"
                for octet in (0, 16, 32, 64, 80, 96, 112, 128, 144, 160, 176, 192, 208, 224, 240)
            ),
            *(f"104.19.{octet}.0/20" for octet in range(0, 256, 16)),
            *(f"104.20.{octet}.0/20" for octet in (0, 16, 32, 48)),
            *(f"104.21.{octet}.0/20" for octet in (0, 16, 32, 48, 64, 80, 96, 112, 192, 208, 224)),
            *(f"104.24.{octet}.0/20" for octet in (0, 16, 32, 48, 64, 80, 128, 144, 160)),
        }

        self.assertEqual(len(supplied_ranges), 100)
        self.assertLessEqual(supplied_ranges, set(entries))
        # Было 30 строк; три из 100 переданных сетей уже присутствовали.
        self.assertEqual(len(entries), 127)
        self.assertEqual(len(entries), len(set(entries)))
        for entry in entries:
            ipaddress.ip_network(entry, strict=False)

    def test_digitalocean_profiles_have_shipped_ipset(self) -> None:
        preset = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        expected_keys = {
            "winws2|ipset=ipset-digitalocean.txt|tcp=80,443-65535",
            "winws2|ipset=ipset-digitalocean.txt|udp=443-65535",
        }
        actual_keys = {
            _profile_catalog_key("winws2", profile)
            for profile in preset.profiles
            if str(profile.name or "").startswith("DigitalOcean ")
        }

        self.assertEqual(actual_keys, expected_keys)

        list_path = PRIVATE_ROOT / "dist" / "lists" / "ipset-digitalocean.txt"
        entries = [
            line.strip()
            for line in list_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(len(entries), 863)
        for entry in entries:
            ipaddress.ip_network(entry, strict=False)

    def test_datacamp_profiles_have_shipped_ipset(self) -> None:
        preset = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        expected_keys = {
            "winws2|ipset=ipset-datacamp.txt|tcp=80,443-65535",
            "winws2|ipset=ipset-datacamp.txt|udp=443-65535",
        }
        actual_keys = {
            _profile_catalog_key("winws2", profile)
            for profile in preset.profiles
            if str(profile.name or "").startswith("Datacamp ")
        }

        self.assertEqual(actual_keys, expected_keys)

        builtin_path = PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2" / "Default v1 (game filter).txt"
        builtin = parse_preset_text(
            builtin_path.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=builtin_path.name,
        )
        builtin_keys = {
            _profile_catalog_key("winws2", profile)
            for profile in builtin.profiles
            if str(profile.name or "").startswith("Datacamp ")
        }
        self.assertEqual(builtin_keys, expected_keys)

        list_path = PRIVATE_ROOT / "dist" / "lists" / "ipset-datacamp.txt"
        raw_lines = list_path.read_text(encoding="utf-8").splitlines()
        entries = [
            line.strip()
            for line in raw_lines
            if line.strip() and not line.lstrip().startswith("#")
        ]

        self.assertEqual(raw_lines[0], "# https://ipinfo.io/AS60068")
        self.assertEqual(len(entries), 179)
        self.assertEqual(len(entries), len(set(entries)))
        networks = [ipaddress.ip_network(entry, strict=False) for entry in entries]
        self.assertEqual(sum(network.version == 4 for network in networks), 100)
        self.assertEqual(sum(network.version == 6 for network in networks), 79)

    def test_ovh_profiles_have_updated_shipped_ipset(self) -> None:
        expected_keys = {
            "winws2|ipset=ipset-ovh.txt|tcp=80,443-65535",
            "winws2|ipset=ipset-ovh.txt|udp=443-65535",
        }
        catalog = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        catalog_profiles = [
            profile
            for profile in catalog.profiles
            if str(profile.name or "").startswith("OVH ")
        ]
        self.assertEqual(len(catalog_profiles), 2)
        self.assertEqual(
            {_profile_catalog_key("winws2", profile) for profile in catalog_profiles},
            expected_keys,
        )

        list_path = PRIVATE_ROOT / "dist" / "lists" / "ipset-ovh.txt"
        raw_lines = list_path.read_text(encoding="utf-8").splitlines()
        entries = [
            line.strip()
            for line in raw_lines
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(raw_lines[0], "# https://ipinfo.io/AS16276")
        self.assertEqual(len(entries), 142)
        self.assertEqual(len(entries), len(set(entries)))
        networks = [ipaddress.ip_network(entry, strict=True) for entry in entries]
        self.assertEqual(sum(network.version == 4 for network in networks), 100)
        self.assertEqual(sum(network.version == 6 for network in networks), 42)
        self.assertTrue(
            {
                "51.254.0.0/15",
                "5.135.0.0/16",
                "213.186.32.0/19",
                "2001:41d0::/32",
                "2001:41d0:ab13::/48",
                "2607:5300:603::/48",
            }.issubset(entries)
        )
        self.assertNotIn("2.57.242.0/24", entries)

    def test_roblox_profiles_have_updated_shipped_ipset(self) -> None:
        expected_keys = {
            "winws2|ipset=ipset-roblox.txt|tcp=80,443-65535",
            "winws2|ipset=ipset-roblox.txt|udp=443-65535",
        }
        catalog = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        catalog_keys = {
            _profile_catalog_key("winws2", profile)
            for profile in catalog.profiles
            if str(profile.name or "").startswith("Roblox ")
        }
        self.assertTrue(expected_keys.issubset(catalog_keys))

        list_path = PRIVATE_ROOT / "dist" / "lists" / "ipset-roblox.txt"
        entries = [
            line.strip()
            for line in list_path.read_text(encoding="utf-8").splitlines()
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(len(entries), 59)
        self.assertEqual(len(entries), len(set(entries)))
        networks = [ipaddress.ip_network(entry, strict=True) for entry in entries]
        self.assertEqual(sum(network.version == 4 for network in networks), 47)
        self.assertEqual(sum(network.version == 6 for network in networks), 12)
        self.assertTrue(
            {
                "128.116.0.0/17",
                "103.140.28.0/23",
                "205.201.62.0/24",
                "2620:135:6000::/40",
                "2620:2b:e000::/48",
                "2620:135:6041::/48",
            }.issubset(entries)
        )
        self.assertTrue(
            {
                "18.165.0.0/16",
                "103.140.0.0/16",
                "2602:801:1000::/48",
            }.isdisjoint(entries)
        )

    def test_novoserve_profiles_have_shipped_ipset(self) -> None:
        expected_keys = {
            "winws2|ipset=ipset-novoserve.txt|tcp=80,443-65535",
            "winws2|ipset=ipset-novoserve.txt|udp=443-65535",
        }
        catalog = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        catalog_profiles = [
            profile
            for profile in catalog.profiles
            if str(profile.name or "").startswith("NovoServe ")
        ]
        self.assertEqual(len(catalog_profiles), 2)
        self.assertEqual(
            {_profile_catalog_key("winws2", profile) for profile in catalog_profiles},
            expected_keys,
        )

        builtin_path = PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2" / "Default v1 (game filter).txt"
        builtin = parse_preset_text(
            builtin_path.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=builtin_path.name,
        )
        builtin_profiles = [
            profile
            for profile in builtin.profiles
            if str(profile.name or "").startswith("NovoServe ")
        ]
        self.assertEqual(len(builtin_profiles), 2)
        self.assertEqual(
            {_profile_catalog_key("winws2", profile) for profile in builtin_profiles},
            expected_keys,
        )
        strategies = {
            str(profile.name): profile.strategy.strategy_lines
            for profile in builtin_profiles
        }
        self.assertEqual(
            strategies,
            {
                "NovoServe TCP": [
                    "--out-range=-d8",
                    "--lua-desync=hostfakesplit:host=ozon.ru:tcp_ts=-1000:tcp_md5:repeats=4",
                ],
                "NovoServe UDP": [
                    "--out-range=-d8",
                    "--lua-desync=fake:blob=stun_pat:repeats=6",
                ],
            },
        )

        list_path = PRIVATE_ROOT / "dist" / "lists" / "ipset-novoserve.txt"
        raw_lines = list_path.read_text(encoding="utf-8").splitlines()
        entries = [
            line.strip()
            for line in raw_lines
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(raw_lines[0], "# https://ipinfo.io/AS204601")
        self.assertEqual(len(entries), 101)
        self.assertEqual(len(entries), len(set(entries)))
        networks = [ipaddress.ip_network(entry, strict=False) for entry in entries]
        self.assertEqual(sum(network.version == 4 for network in networks), 100)
        self.assertEqual(sum(network.version == 6 for network in networks), 1)
        self.assertTrue(
            {
                "45.81.224.0/22",
                "185.213.210.0/24",
                "2a07:5980::/29",
            }.issubset(entries)
        )

    def test_fastly_profiles_have_shipped_ipset(self) -> None:
        expected_keys = {
            "winws2|ipset=ipset-fastly.txt|tcp=80,443-65535",
            "winws2|ipset=ipset-fastly.txt|udp=443-65535",
        }
        catalog = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        catalog_profiles = [
            profile
            for profile in catalog.profiles
            if str(profile.name or "").startswith("Fastly ")
        ]
        self.assertEqual(len(catalog_profiles), 2)
        self.assertEqual(
            {_profile_catalog_key("winws2", profile) for profile in catalog_profiles},
            expected_keys,
        )

        builtin_path = PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2" / "Default v1 (game filter).txt"
        builtin = parse_preset_text(
            builtin_path.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=builtin_path.name,
        )
        builtin_profiles = [
            profile
            for profile in builtin.profiles
            if str(profile.name or "").startswith("Fastly ")
        ]
        self.assertEqual(len(builtin_profiles), 2)
        self.assertEqual(
            {_profile_catalog_key("winws2", profile) for profile in builtin_profiles},
            expected_keys,
        )
        strategies = {
            str(profile.name): profile.strategy.strategy_lines
            for profile in builtin_profiles
        }
        self.assertEqual(
            strategies,
            {
                "Fastly TCP": [
                    "--out-range=-d8",
                    "--payload=tls_client_hello",
                    "--lua-desync=multisplit:pos=1,host+2,sld+2,sld+5,sniext+1,sniext+2,endhost-2:seqovl=1",
                ],
                "Fastly UDP": [
                    "--out-range=-n8",
                    "--payload=all",
                    "--lua-desync=fake:repeats=6:blob=fake_default_quic",
                ],
            },
        )

        list_path = PRIVATE_ROOT / "dist" / "lists" / "ipset-fastly.txt"
        raw_lines = list_path.read_text(encoding="utf-8").splitlines()
        entries = [
            line.strip()
            for line in raw_lines
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(raw_lines[0], "# https://ipinfo.io/AS54113")
        self.assertEqual(len(entries), 200)
        self.assertEqual(len(entries), len(set(entries)))
        networks = [ipaddress.ip_network(entry, strict=False) for entry in entries]
        self.assertEqual(sum(network.version == 4 for network in networks), 100)
        self.assertEqual(sum(network.version == 6 for network in networks), 100)
        self.assertTrue(
            {
                "151.101.0.0/16",
                "151.101.156.0/22",
                "2a04:4e42::/32",
                "2a00:8c40:f000::/44",
            }.issubset(entries)
        )

    def test_default_v1_uses_single_facebook_ipset_profile(self) -> None:
        expected_key = "winws2|ipset=ipset-facebook.txt|tcp=80,443"
        catalog = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        facebook_catalog_keys = {
            _profile_catalog_key("winws2", profile)
            for profile in catalog.profiles
            if str(profile.name or "") == "Facebook"
        }
        self.assertIn(expected_key, facebook_catalog_keys)

        builtin_path = PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2" / "Default v1 (game filter).txt"
        builtin_text = builtin_path.read_text(encoding="utf-8")
        builtin = parse_preset_text(
            builtin_text,
            engine="winws2",
            source_name=builtin_path.name,
        )
        meta_profiles = [
            profile
            for profile in builtin.profiles
            if str(profile.name or "") in {"Facebook", "Instagram"}
        ]
        self.assertEqual(len(meta_profiles), 1)
        self.assertEqual(str(meta_profiles[0].name), "Facebook")
        self.assertEqual(_profile_catalog_key("winws2", meta_profiles[0]), expected_key)
        self.assertEqual(
            meta_profiles[0].strategy.strategy_lines,
            [
                "--out-range=-d10",
                "--payload=tls_client_hello",
                "--lua-desync=hostfakesplit_multi:hosts=google.com,vimeo.com:tcp_ts=-1000:tcp_md5:repeats=2",
            ],
        )
        self.assertNotIn("--hostlist=lists/facebook.txt", builtin_text)
        self.assertNotIn("--hostlist=lists/instagram.txt", builtin_text)

        list_path = PRIVATE_ROOT / "dist" / "lists" / "ipset-facebook.txt"
        raw_lines = list_path.read_text(encoding="utf-8").splitlines()
        entries = [
            line.strip()
            for line in raw_lines
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(raw_lines[0], "# https://ipinfo.io/AS32934")
        self.assertEqual(len(entries), 202)
        self.assertEqual(len(entries), len(set(entries)))
        networks = [ipaddress.ip_network(entry, strict=True) for entry in entries]
        self.assertEqual(sum(network.version == 4 for network in networks), 101)
        self.assertEqual(sum(network.version == 6 for network in networks), 101)
        self.assertTrue(
            {
                "57.144.0.0/14",
                "163.70.151.0/24",
                "129.134.28.0/23",
                "2a03:2880::/32",
                "2620:0:1c00::/40",
                "2a03:2880:f213::/48",
            }.issubset(entries)
        )
        self.assertNotIn("157.144.0.0/16", entries)

    def test_frantech_solutions_profiles_have_shipped_ipset(self) -> None:
        expected_keys = {
            "winws2|ipset=ipset-frantech.txt|tcp=80,443-65535",
            "winws2|ipset=ipset-frantech.txt|udp=443-65535",
        }
        catalog = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        catalog_profiles = [
            profile
            for profile in catalog.profiles
            if str(profile.name or "").startswith("FranTech Solutions ")
        ]
        self.assertEqual(len(catalog_profiles), 2)
        self.assertEqual(
            {_profile_catalog_key("winws2", profile) for profile in catalog_profiles},
            expected_keys,
        )

        builtin_path = PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2" / "Default v1 (game filter).txt"
        builtin = parse_preset_text(
            builtin_path.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=builtin_path.name,
        )
        builtin_profiles = [
            profile
            for profile in builtin.profiles
            if str(profile.name or "").startswith("FranTech Solutions ")
        ]
        self.assertEqual(len(builtin_profiles), 2)
        self.assertEqual(
            {_profile_catalog_key("winws2", profile) for profile in builtin_profiles},
            expected_keys,
        )
        strategies = {
            str(profile.name): profile.strategy.strategy_lines
            for profile in builtin_profiles
        }
        self.assertEqual(
            strategies,
            {
                "FranTech Solutions TCP": [
                    "--out-range=-d8",
                    "--lua-desync=hostfakesplit:host=ozon.ru:tcp_ts=-1000:tcp_md5:repeats=4",
                ],
                "FranTech Solutions UDP": [
                    "--out-range=-d8",
                    "--lua-desync=fake:blob=stun_pat:repeats=6",
                ],
            },
        )

        list_path = PRIVATE_ROOT / "dist" / "lists" / "ipset-frantech.txt"
        raw_lines = list_path.read_text(encoding="utf-8").splitlines()
        entries = [
            line.strip()
            for line in raw_lines
            if line.strip() and not line.lstrip().startswith("#")
        ]
        self.assertEqual(raw_lines[0], "# https://ipinfo.io/AS53667")
        self.assertEqual(len(entries), 78)
        self.assertEqual(len(entries), len(set(entries)))
        networks = [ipaddress.ip_network(entry, strict=True) for entry in entries]
        self.assertEqual(sum(network.version == 4 for network in networks), 43)
        self.assertEqual(sum(network.version == 6 for network in networks), 35)
        self.assertTrue(
            {
                "209.141.32.0/19",
                "23.183.81.0/24",
                "198.251.90.0/24",
                "209.141.39.0/24",
                "2a09:7500::/29",
                "2605:6400:c000::/34",
                "2a14:7581:d104::/48",
            }.issubset(entries)
        )

    def test_railway_profiles_have_shipped_ipset(self) -> None:
        expected_keys = {
            "winws2|ipset=ipset-railway.txt|tcp=80,443-65535",
            "winws2|ipset=ipset-railway.txt|udp=443-65535",
        }
        catalog = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        catalog_profiles = [
            profile
            for profile in catalog.profiles
            if str(profile.name or "").startswith("Railway ")
        ]
        self.assertEqual(len(catalog_profiles), 2)
        self.assertEqual(
            {_profile_catalog_key("winws2", profile) for profile in catalog_profiles},
            expected_keys,
        )

        builtin_path = PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2" / "Default v1 (game filter).txt"
        builtin = parse_preset_text(
            builtin_path.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=builtin_path.name,
        )
        builtin_profiles = [
            profile
            for profile in builtin.profiles
            if str(profile.name or "").startswith("Railway ")
        ]
        self.assertEqual(len(builtin_profiles), 2)
        self.assertEqual(
            {_profile_catalog_key("winws2", profile) for profile in builtin_profiles},
            expected_keys,
        )
        strategies = {
            str(profile.name): profile.strategy.strategy_lines
            for profile in builtin_profiles
        }
        self.assertEqual(
            strategies,
            {
                "Railway TCP": [
                    "--out-range=-d8",
                    "--payload=tls_client_hello",
                    "--lua-desync=multisplit:pos=1,host+2,sld+2,sld+5,sniext+1,sniext+2,endhost-2:seqovl=1",
                ],
                "Railway UDP": [
                    "--out-range=-n8",
                    "--payload=all",
                    "--lua-desync=fake:repeats=6:blob=fake_default_quic",
                ],
            },
        )

        list_path = PRIVATE_ROOT / "dist" / "lists" / "ipset-railway.txt"
        raw_lines = list_path.read_text(encoding="utf-8").splitlines()
        entries = [
            line.strip()
            for line in raw_lines
            if line.strip() and not line.lstrip().startswith("#")
        ]
        expected_entries = {
            "66.33.22.0/23",
            "66.33.23.0/24",
            "69.46.46.0/24",
            "152.55.176.0/22",
            "152.55.180.0/22",
            "152.55.184.0/22",
            "162.220.232.0/23",
            "162.220.234.0/23",
            "208.77.244.0/23",
            "208.77.246.0/23",
            "2607:99c0::/40",
            "2607:99c0:100::/40",
            "2607:99c0:200::/40",
            "2607:99c0:300::/40",
            "2607:99c0:800::/40",
            "2607:99c0:900::/40",
            "2607:99c0:a00::/40",
        }
        self.assertEqual(raw_lines[0], "# https://bgp.he.net/AS400940")
        self.assertEqual(len(entries), 17)
        self.assertEqual(set(entries), expected_entries)
        networks = [ipaddress.ip_network(entry, strict=True) for entry in entries]
        self.assertEqual(sum(network.version == 4 for network in networks), 10)
        self.assertEqual(sum(network.version == 6 for network in networks), 7)

    def test_google_cloud_profiles_have_shipped_usa_google_ipset(self) -> None:
        preset = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        expected_keys = {
            "winws2|ipset=ipset-usa-google.txt|tcp=80,443-65535",
            "winws2|ipset=ipset-usa-google.txt|udp=443-65535",
        }
        catalog_profiles = [
            profile
            for profile in preset.profiles
            if str(profile.name or "").startswith("Google Cloud ")
        ]
        actual_keys = {
            _profile_catalog_key("winws2", profile)
            for profile in catalog_profiles
        }

        self.assertEqual(
            {str(profile.name) for profile in catalog_profiles},
            {"Google Cloud TCP", "Google Cloud UDP"},
        )
        self.assertEqual(actual_keys, expected_keys)

        builtin_path = PUBLIC_ROOT / "src" / "presets" / "builtin" / "winws2" / "Default v1 (game filter).txt"
        builtin = parse_preset_text(
            builtin_path.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=builtin_path.name,
        )
        builtin_profiles = [
            profile
            for profile in builtin.profiles
            if str(profile.name or "").startswith("Google Cloud ")
        ]
        builtin_keys = {
            _profile_catalog_key("winws2", profile)
            for profile in builtin_profiles
        }
        self.assertEqual(
            {str(profile.name) for profile in builtin_profiles},
            {"Google Cloud TCP", "Google Cloud UDP"},
        )
        self.assertEqual(builtin_keys, expected_keys)

        list_path = PRIVATE_ROOT / "dist" / "lists" / "ipset-usa-google.txt"
        raw_lines = list_path.read_text(encoding="utf-8").splitlines()
        entries = [
            line.strip()
            for line in raw_lines
            if line.strip() and not line.lstrip().startswith("#")
        ]

        self.assertEqual(raw_lines[0], "# https://ipinfo.io/AS396982")
        self.assertEqual(len(entries), 200)
        self.assertEqual(len(entries), len(set(entries)))
        networks = [ipaddress.ip_network(entry, strict=False) for entry in entries]
        self.assertEqual(sum(network.version == 4 for network in networks), 100)
        self.assertEqual(sum(network.version == 6 for network in networks), 100)

    def test_builtin_presets_do_not_put_wide_discord_tcp_filter_on_other_lists(self) -> None:
        template_keys = _all_profile_keys()
        offenders: list[str] = []

        for engine in ("winws1", "winws2"):
            for path in sorted((PUBLIC_ROOT / "src" / "presets" / "builtin" / engine).glob("*.txt")):
                preset = parse_preset_text(
                    path.read_text(encoding="utf-8", errors="replace"),
                    engine=engine,
                    source_name=path.name,
                )
                for profile in preset.profiles:
                    if WIDE_DISCORD_TCP_FILTER not in profile.match.filter_lines:
                        continue
                    primary_lines = set(profile.match.hostlist_lines + profile.match.ipset_lines + profile.match.hostlist_domains_lines)
                    logical_key = build_profile_logical_key(profile.match_signature)
                    if primary_lines not in ({line} for line in WIDE_DISCORD_PRIMARY_LINES) or logical_key not in template_keys:
                        offenders.append(f"{engine}/{path.name} profile {profile.index}: {profile.display_name}")

        self.assertEqual(offenders, [])

    def test_builtin_presets_keep_known_launch_presets_that_are_not_ui_templates(self) -> None:
        """Builtin preset-ы являются runtime-ресурсами, а не копией all_profiles.txt.

        all_profiles.txt описывает библиотеку profile-ов для GUI. Встроенные preset-ы
        могут содержать технические all-sites, circular, voice и winws1 блоки, которых
        нет в этой библиотеке, но они всё равно должны оставаться в поставке.
        """
        known_presets = (
            ("winws1", "discord_voice_dtls.txt"),
            ("winws1", "alt10_190b_allsites.txt"),
            ("winws2", "ALL TCP & UDP discord_urgent_sni.txt"),
            ("winws2", "Default (circular).txt"),
            ("winws2", "syndata (circular).txt"),
        )
        offenders: list[str] = []

        for engine, file_name in known_presets:
            path = PUBLIC_ROOT / "src" / "presets" / "builtin" / engine / file_name
            if not path.exists():
                offenders.append(f"{engine}/{file_name}: missing")
                continue
            preset = parse_preset_text(
                path.read_text(encoding="utf-8", errors="replace"),
                engine=engine,
                source_name=path.name,
            )
            if not preset.profiles:
                offenders.append(f"{engine}/{file_name}: empty")

        self.assertEqual(offenders, [])

    def test_all_profiles_does_not_absorb_runtime_only_all_sites_templates(self) -> None:
        """all_profiles.txt не должен становиться авто-свалкой runtime-only блоков.

        Такие блоки правятся в builtin preset-ах вручную. Добавление их в библиотеку
        profile-ов маскирует проблему матчинга и потом провоцирует опасную чистку
        preset-ов по принципу "нет в all_profiles, значит удалить".
        """
        preset = parse_preset_text(
            ALL_PROFILES_PATH.read_text(encoding="utf-8"),
            engine="winws2",
            source_name=ALL_PROFILES_PATH.name,
        )
        offenders: list[str] = []

        for profile in preset.profiles:
            has_regular_list = bool(
                profile.match.hostlist_lines
                or profile.match.ipset_lines
                or profile.match.hostlist_domains_lines
            )
            if has_regular_list:
                continue
            has_all_sites_excludes = bool(
                profile.match.hostlist_exclude_lines
                or profile.match.ipset_exclude_lines
            )
            profile_name = str(profile.display_name or "").strip().lower()
            is_allowed_exclude_template = profile_name.startswith("все сайты ") or profile_name == "исключения"
            if has_all_sites_excludes and not is_allowed_exclude_template:
                offenders.append(f"profile {profile.index}: {profile.display_name}")

        self.assertEqual(offenders, [])

    def test_builtin_presets_are_not_empty(self) -> None:
        offenders: list[str] = []

        for engine in ("winws1", "winws2"):
            for path in sorted((PUBLIC_ROOT / "src" / "presets" / "builtin" / engine).glob("*.txt")):
                preset = parse_preset_text(
                    path.read_text(encoding="utf-8", errors="replace"),
                    engine=engine,
                    source_name=path.name,
                )
                if not preset.profiles:
                    offenders.append(f"{engine}/{path.name}")

        self.assertEqual(offenders, [])

    def test_all_profiles_have_logical_keys(self) -> None:
        offenders: list[str] = []

        for engine in ("winws1", "winws2"):
            preset = parse_preset_text(
                ALL_PROFILES_PATH.read_text(encoding="utf-8"),
                engine=engine,
                source_name=ALL_PROFILES_PATH.name,
            )
            for profile in preset.profiles:
                if not build_profile_logical_key(profile.match_signature):
                    offenders.append(f"{engine} profile {profile.index}: {profile.display_name}")

        self.assertEqual(offenders, [])

    def test_builtin_profiles_are_catalog_profiles_wider_profiles_or_runtime_only(self) -> None:
        catalog = _all_profile_catalog()
        offenders: list[str] = []

        for engine in ("winws1", "winws2"):
            for path in sorted((PUBLIC_ROOT / "src" / "presets" / "builtin" / engine).glob("*.txt")):
                preset = parse_preset_text(
                    path.read_text(encoding="utf-8", errors="replace"),
                    engine=engine,
                    source_name=path.name,
                )
                for profile in preset.profiles:
                    profile_key = _profile_catalog_key(engine, profile)
                    target_key = _profile_target_key(profile)
                    filter_key = _profile_filter_key(profile)
                    candidates = catalog.get(target_key, [])
                    exact = next((candidate for candidate in candidates if _profile_filter_key(candidate) == filter_key), None)
                    if exact is not None:
                        _append_name_offender(offenders, engine, path.name, profile, exact)
                        continue

                    if not _profile_primary_target_parts(profile):
                        if profile_key not in RUNTIME_ONLY_PROFILE_KEYS:
                            offenders.append(
                                f"{engine}/{path.name} profile {profile.index}: нет в all_profiles и нет в runtime-only "
                                f"{_format_key(target_key, filter_key)}"
                            )
                        continue

                    same_protocol = [
                        candidate
                        for candidate in candidates
                        if _filter_protocols(_profile_filter_key(candidate)) == _filter_protocols(filter_key)
                    ]
                    narrower_than_catalog = _widest_profile(
                        candidate
                        for candidate in same_protocol
                        if _filter_ports_are_subset(filter_key, _profile_filter_key(candidate))
                    )
                    if narrower_than_catalog is not None:
                        if profile_key in ACCEPTED_NARROWER_PROFILE_KEYS:
                            continue
                        offenders.append(
                            f"{engine}/{path.name} profile {profile.index}: заменить на канон "
                            f"{narrower_than_catalog.name!r} "
                            f"{_format_key(_profile_target_key(narrower_than_catalog), _profile_filter_key(narrower_than_catalog))}; "
                            f"сейчас {_format_key(target_key, filter_key)}"
                        )
                        continue

                    wider_than_catalog = _widest_profile(
                        candidate
                        for candidate in same_protocol
                        if _filter_ports_are_subset(_profile_filter_key(candidate), filter_key)
                    )
                    if wider_than_catalog is not None:
                        if profile_key not in ACCEPTED_WIDER_PROFILE_KEYS:
                            offenders.append(
                                f"{engine}/{path.name} profile {profile.index}: широкая версия не подтверждена "
                                f"{_format_key(target_key, filter_key)}"
                            )
                            continue
                        _append_name_offender(offenders, engine, path.name, profile, wider_than_catalog)
                        continue

                    if profile_key not in RUNTIME_ONLY_PROFILE_KEYS:
                        offenders.append(
                            f"{engine}/{path.name} profile {profile.index}: нет в all_profiles и нет в runtime-only "
                            f"{_format_key(target_key, filter_key)}"
                        )

        self.assertEqual(offenders, [])


def _all_profile_keys() -> set[str]:
    preset = parse_preset_text(
        ALL_PROFILES_PATH.read_text(encoding="utf-8"),
        engine="winws2",
        source_name=ALL_PROFILES_PATH.name,
    )
    return {
        build_profile_logical_key(profile.match_signature)
        for profile in preset.profiles
        if build_profile_logical_key(profile.match_signature)
    }


def _find_profile(profiles, name: str, match_lines: tuple[str, ...]):
    for profile in profiles:
        if str(profile.name or "").strip() != name:
            continue
        if profile.match.all_lines() == list(match_lines):
            return profile
    return None


def _all_profile_catalog():
    preset = parse_preset_text(
        ALL_PROFILES_PATH.read_text(encoding="utf-8"),
        engine="winws2",
        source_name=ALL_PROFILES_PATH.name,
    )
    result: dict[tuple[str, ...], list] = {}
    for profile in preset.profiles:
        result.setdefault(_profile_target_key(profile), []).append(profile)
    return result


def _all_profile_names_by_key(names: set[str]) -> dict[str, str]:
    preset = parse_preset_text(
        ALL_PROFILES_PATH.read_text(encoding="utf-8"),
        engine="winws2",
        source_name=ALL_PROFILES_PATH.name,
    )
    result: dict[str, str] = {}
    for profile in preset.profiles:
        clean_name = str(profile.name or "").strip()
        if clean_name not in names:
            continue
        logical_key = build_profile_logical_key(profile.match_signature)
        if logical_key:
            result[logical_key] = clean_name
    return result


def _all_profile_unique_names_by_key() -> dict[str, str]:
    preset = parse_preset_text(
        ALL_PROFILES_PATH.read_text(encoding="utf-8"),
        engine="winws2",
        source_name=ALL_PROFILES_PATH.name,
    )
    names_by_key: dict[str, set[str]] = {}
    for profile in preset.profiles:
        logical_key = build_profile_logical_key(profile.match_signature)
        clean_name = str(profile.name or "").strip()
        if logical_key and clean_name:
            names_by_key.setdefault(logical_key, set()).add(clean_name)
    return {
        key: next(iter(names))
        for key, names in names_by_key.items()
        if len(names) == 1
    }


def _profile_catalog_key(engine: str, profile) -> str:
    return f"{engine}|{_format_key(_profile_target_key(profile), _profile_filter_key(profile))}"


def _profile_target_key(profile) -> tuple[str, ...]:
    primary = _profile_primary_target_parts(profile)
    if primary:
        return primary

    parts: list[str] = []
    for line in profile.match.hostlist_exclude_lines:
        option, value = _split_profile_option(line)
        kind = option.removeprefix("--")
        parts.append(f"{kind}={_normalize_profile_value(kind, value)}")
    for line in profile.match.hostlist_auto_lines:
        option, value = _split_profile_option(line)
        kind = option.removeprefix("--")
        parts.append(f"{kind}={_normalize_profile_value(kind, value)}")
    for line in profile.match.ipset_exclude_lines:
        option, value = _split_profile_option(line)
        kind = option.removeprefix("--")
        parts.append(f"{kind}={_normalize_profile_value(kind, value)}")
    return tuple(sorted(parts))


def _profile_primary_target_parts(profile) -> tuple[str, ...]:
    parts: list[str] = []
    for kind, lines in (
        ("hostlist", profile.match.hostlist_lines),
        ("ipset", profile.match.ipset_lines),
        ("hostlist-domains", profile.match.hostlist_domains_lines),
        ("ipset-ip", profile.match.inline_ipset_lines),
    ):
        for line in lines:
            _option, value = _split_profile_option(line)
            parts.append(f"{kind}={_normalize_profile_value(kind, value)}")
    return tuple(sorted(parts))


def _profile_filter_key(profile) -> tuple[str, ...]:
    parts: list[str] = []
    for line in profile.match.filter_lines:
        option, value = _split_profile_option(line)
        if option == "--filter-tcp":
            parts.append(f"tcp={value}")
        elif option == "--filter-udp":
            parts.append(f"udp={value}")
        elif option == "--filter-l7":
            parts.append(f"l7={value.lower()}")
    return tuple(sorted(parts))


def _filter_protocols(filter_key: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(part.split("=", 1)[0] for part in filter_key)


def _filter_ports_are_subset(left: tuple[str, ...], right: tuple[str, ...]) -> bool:
    if _filter_protocols(left) != _filter_protocols(right):
        return False
    left_values = dict(part.split("=", 1) for part in left)
    right_values = dict(part.split("=", 1) for part in right)
    for protocol, left_value in left_values.items():
        right_value = right_values.get(protocol, "")
        if protocol == "l7":
            if left_value != right_value:
                return False
            continue
        left_ports = _parse_ports(left_value)
        right_ports = _parse_ports(right_value)
        if left_ports is None or right_ports is None:
            return left_value == right_value
        if not left_ports.issubset(right_ports):
            return False
    return True


def _widest_profile(profiles) -> object | None:
    candidates = list(profiles)
    if not candidates:
        return None
    return max(candidates, key=lambda profile: _filter_port_weight(_profile_filter_key(profile)))


def _filter_port_weight(filter_key: tuple[str, ...]) -> int:
    weight = 0
    for part in filter_key:
        protocol, _sep, value = part.partition("=")
        if protocol == "l7":
            weight += 1
            continue
        ports = _parse_ports(value)
        if ports is not None:
            weight += len(ports)
    return weight


def _parse_ports(value: str) -> set[int] | None:
    ports: set[int] = set()
    for raw_part in str(value or "").split(","):
        part = raw_part.strip()
        if not part:
            continue
        if "-" in part:
            start, _sep, end = part.partition("-")
            try:
                ports.update(range(int(start), int(end) + 1))
            except ValueError:
                return None
            continue
        try:
            ports.add(int(part))
        except ValueError:
            return None
    return ports


def _split_profile_option(line: str) -> tuple[str, str]:
    stripped = str(line or "").strip()
    if "=" not in stripped:
        return stripped.lower(), ""
    option, _sep, value = stripped.partition("=")
    return option.strip().lower(), value.strip()


def _normalize_profile_value(kind: str, value: str) -> str:
    clean = str(value or "").strip().strip('"').strip("'")
    if kind in {"hostlist", "hostlist-exclude", "hostlist-auto", "ipset", "ipset-exclude"}:
        return PureWindowsPath(clean.lstrip("@").replace("\\", "/")).name.lower()
    if kind in {"hostlist-domains", "hostlist-exclude-domains", "ipset-ip", "ipset-exclude-ip"}:
        return ",".join(sorted(token.strip().lower() for token in clean.split(",") if token.strip()))
    return clean.lower()


def _format_key(target_key: tuple[str, ...], filter_key: tuple[str, ...]) -> str:
    return f"{';'.join(target_key) or '(none)'}|{';'.join(filter_key) or '(none)'}"


def _append_name_offender(offenders: list[str], engine: str, file_name: str, profile, catalog_profile) -> None:
    expected_name = str(catalog_profile.name or "").strip()
    if expected_name and str(profile.name or "").strip() != expected_name:
        offenders.append(
            f"{engine}/{file_name} profile {profile.index}: "
            f"name {profile.name!r} != {expected_name!r}"
        )


def _profile_has_udp_port_80(profile) -> bool:
    for line in getattr(profile.match, "filter_lines", ()) or ():
        stripped = str(line or "").strip().lower()
        if not stripped.startswith("--filter-udp="):
            continue
        value = stripped.split("=", 1)[1]
        for part in value.split(","):
            token = part.strip()
            if token == "80" or token.startswith("80-"):
                return True
    return False


class _SelectedPresetStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def read_selected_preset_source(self, _launch_method: str):
        return self._path.read_text(encoding="utf-8", errors="replace"), SimpleNamespace(
            file_name=self._path.name,
            name=self._path.stem,
        )

    def save_selected_preset_source(self, _launch_method: str, _text: str) -> None:
        raise AssertionError("real builtin e2e test must not rewrite preset")


def _items_with_match_line(items, expected_line: str):
    return [
        item
        for item in items
        if expected_line in getattr(item, "match_lines", ())
    ]


def _list_entries(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


if __name__ == "__main__":
    unittest.main()
