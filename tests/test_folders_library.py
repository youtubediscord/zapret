from __future__ import annotations

import unittest

from folders.defaults import (
    COMMON_FOLDER_KEY,
    PINNED_FOLDER_KEY,
    build_default_preset_folders,
    build_default_profile_folders,
    classify_preset_folder,
    classify_profile_folder,
)
from folders.ordering import build_folder_rows
from folders.store import FolderLibraryStore, normalize_folder_state


class FolderDefaultsTests(unittest.TestCase):
    def test_default_preset_folders_have_strict_order(self) -> None:
        state = build_default_preset_folders()

        self.assertEqual(
            [folder["name"] for folder in state["folders"].values()],
            ["ALL TCP & UDP", "Общие", "1.9.9", "Game filter", "Circular"],
        )
        self.assertEqual(state["folders"][COMMON_FOLDER_KEY]["system"], True)

    def test_winws1_default_preset_folders_have_199a_group(self) -> None:
        state = build_default_preset_folders("winws1")

        self.assertEqual(
            [folder["name"] for folder in state["folders"].values()],
            [
                "Все сайты",
                "1.9.9a",
                "ALT",
                "Игры",
                "YouTube",
                "Discord",
                "Провайдеры",
                "Bolvan",
                "Fake TLS",
                "Split / MD5 / TTL",
                "Общие",
            ],
        )
        self.assertEqual(state["folders"][COMMON_FOLDER_KEY]["system"], True)

    def test_default_profile_folders_have_common_and_all_sites_at_the_end(self) -> None:
        state = build_default_profile_folders()

        self.assertEqual(
            [folder["name"] for folder in state["folders"].values()],
            [
                "YouTube",
                "Discord",
                "GitHub",
                "Мессенджеры",
                "Соцсети",
                "Игры",
                "Roblox",
                "Amazon",
                "Хостеры",
                "Сайты",
                "ZapretKVN",
                "Общие",
                "Все сайты",
            ],
        )
        self.assertEqual(state["folders"][COMMON_FOLDER_KEY]["system"], True)

    def test_preset_default_folder_is_classified_from_known_name(self) -> None:
        self.assertEqual(classify_preset_folder("ALL TCP & UDP v3_2.txt"), "all-tcp-udp")
        self.assertEqual(classify_preset_folder("Default (circular).txt"), "circular")
        self.assertEqual(classify_preset_folder("general ALT10 1.9.9 (game filter).txt"), "1-9-9")
        self.assertEqual(classify_preset_folder("Preset X (game filter).txt"), "game-filter")
        self.assertEqual(classify_preset_folder("Unknown custom.txt"), COMMON_FOLDER_KEY)

    def test_winws1_199a_preset_wins_over_alt_and_game_filter(self) -> None:
        self.assertEqual(
            classify_preset_folder("general ALT10 1.9.9a (game filter).txt", "winws1"),
            "1-9-9a",
        )

    def test_profile_default_folder_is_classified_from_profile_text(self) -> None:
        self.assertEqual(classify_profile_folder("YouTube Russia CDN --hostlist=youtube.txt"), "youtube")
        self.assertEqual(
            classify_profile_folder("i.ytimg.com (превью роликов) --hostlist=lists/i.ytimg.txt"),
            "youtube",
        )
        self.assertEqual(classify_profile_folder("Discord Updates --hostlist=discord.txt"), "discord")
        self.assertEqual(classify_profile_folder("vencord.dev --hostlist=lists/vencord.txt"), "discord")
        self.assertEqual(classify_profile_folder("GitHub --hostlist=lists/github.txt"), "github")
        self.assertEqual(
            classify_profile_folder("githubusercontent.com --hostlist=lists/githubusercontent.txt"),
            "github",
        )
        self.assertEqual(classify_profile_folder("Telegram --hostlist=telegram.txt"), "messengers")
        self.assertEqual(classify_profile_folder("Facebook --hostlist=facebook.txt"), "social")
        self.assertEqual(classify_profile_folder("Valorant game filter"), "games")
        self.assertEqual(classify_profile_folder("itch.io --hostlist=lists/itch.txt"), "games")
        self.assertEqual(classify_profile_folder("roblox --ipset=lists/ipset-roblox.txt"), "roblox")
        self.assertEqual(classify_profile_folder("tr.rbxcdn.com --hostlist=lists/tr-rbxcdn-com.txt"), "roblox")
        self.assertEqual(classify_profile_folder("Tanki X --hostlist=lists/tankix.txt"), "games")
        self.assertEqual(classify_profile_folder("EpicGames & Fortnite --hostlist=lists/epicgames-fortnite.txt"), "games")
        self.assertEqual(classify_profile_folder("Ubisoft --hostlist=lists/ubisoft.txt"), "games")
        self.assertEqual(classify_profile_folder("lol-ru --ipset=lists/ipset-lol-ru.txt"), "games")
        self.assertEqual(classify_profile_folder("cloudflare --ipset=lists/ipset-cloudflare.txt"), "hosters")
        self.assertEqual(classify_profile_folder("amazon --ipset=lists/ipset-amazon.txt"), "amazon")
        self.assertEqual(classify_profile_folder("cloudfront.net --hostlist=lists/cloudfront.txt"), "amazon")
        self.assertEqual(classify_profile_folder("datacamp --ipset=lists/ipset-datacamp.txt"), "hosters")
        self.assertEqual(classify_profile_folder("digitalocean --ipset=lists/ipset-digitalocean.txt"), "hosters")
        self.assertEqual(classify_profile_folder("ovh --ipset=lists/ipset-ovh.txt"), "hosters")
        self.assertEqual(classify_profile_folder("hetzner --ipset=lists/ipset-hetzner.txt"), "hosters")
        self.assertEqual(classify_profile_folder("timeweb --ipset=lists/ipset-timeweb.txt"), "zapretkvn")
        self.assertEqual(classify_profile_folder("zapretkvn --ipset=lists/ipset-zapretkvn.txt"), "zapretkvn")
        self.assertEqual(classify_profile_folder("--filter-tcp=80,443 --hostlist-exclude=ru.txt"), "all-sites")
        self.assertEqual(classify_profile_folder("rutracker.org"), "sites")

    def test_profile_folder_normalization_merges_new_default_folders(self) -> None:
        old_state = {
            "folders": {
                "youtube": {"name": "YouTube", "order": 0},
                "discord": {"name": "Discord", "order": 1},
                "messengers": {"name": "Мессенджеры", "order": 2},
                "social": {"name": "Соцсети", "order": 3},
                "games": {"name": "Игры", "order": 4},
                "sites": {"name": "Сайты", "order": 5},
                "common": {"name": "Общие", "order": 6, "system": True},
                "all-sites": {"name": "Все сайты", "order": 7},
            },
            "items": {},
        }

        normalized = normalize_folder_state(old_state, build_default_profile_folders())
        ordered_names = [
            folder["name"]
            for _key, folder in sorted(normalized["folders"].items(), key=lambda pair: pair[1]["order"])
        ]

        self.assertEqual(
            ordered_names,
            [
                "YouTube",
                "Discord",
                "GitHub",
                "Мессенджеры",
                "Соцсети",
                "Игры",
                "Roblox",
                "Amazon",
                "Хостеры",
                "Сайты",
                "ZapretKVN",
                "Общие",
                "Все сайты",
            ],
        )


class FolderOrderingTests(unittest.TestCase):
    def test_manual_order_wins_over_rating_then_name(self) -> None:
        state = build_default_preset_folders()
        state["items"] = {
            "manual-second.txt": {"folder_key": COMMON_FOLDER_KEY, "order": 1, "rating": 10},
            "manual-first.txt": {"folder_key": COMMON_FOLDER_KEY, "order": 0, "rating": 0},
            "rated.txt": {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 9},
            "alpha.txt": {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 0},
        }
        rows = build_folder_rows(
            state,
            live_items=[
                {"key": "alpha.txt", "name": "Alpha", "rating": 0},
                {"key": "rated.txt", "name": "Rated", "rating": 9},
                {"key": "manual-second.txt", "name": "Manual Second", "rating": 10},
                {"key": "manual-first.txt", "name": "Manual First", "rating": 0},
            ],
        )

        item_keys = [row["key"] for row in rows if row["kind"] == "item"]
        self.assertEqual(item_keys, ["manual-first.txt", "manual-second.txt", "rated.txt", "alpha.txt"])

    def test_pinned_items_are_rendered_in_service_folder_above_regular_folders(self) -> None:
        state = build_default_preset_folders()
        state["items"] = {
            "regular.txt": {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 0},
            "pinned.txt": {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 0, "pinned": True},
        }

        rows = build_folder_rows(
            state,
            live_items=[
                {"key": "regular.txt", "name": "Regular", "rating": 0},
                {"key": "pinned.txt", "name": "Pinned", "rating": 0, "pinned": True},
            ],
            include_pinned_folder=True,
        )

        self.assertEqual(rows[0]["kind"], "folder")
        self.assertEqual(rows[0]["key"], PINNED_FOLDER_KEY)
        self.assertEqual(rows[1]["kind"], "item")
        self.assertEqual(rows[1]["key"], "pinned.txt")

    def test_collapsed_pinned_service_folder_hides_pinned_items(self) -> None:
        state = build_default_preset_folders()
        state["folders"][PINNED_FOLDER_KEY] = {
            "name": "Закрепленные",
            "order": 0,
            "collapsed": True,
            "system": True,
        }
        state["items"] = {
            "pinned.txt": {"folder_key": COMMON_FOLDER_KEY, "order": None, "rating": 0, "pinned": True},
        }

        rows = build_folder_rows(
            state,
            live_items=[
                {"key": "pinned.txt", "name": "Pinned", "rating": 0, "pinned": True},
            ],
            include_pinned_folder=True,
        )

        self.assertEqual(rows[0]["kind"], "folder")
        self.assertEqual(rows[0]["key"], PINNED_FOLDER_KEY)
        self.assertNotIn("pinned.txt", [row.get("key") for row in rows if row["kind"] == "item"])


class FolderStoreTests(unittest.TestCase):
    def test_folder_rename_and_move_skip_unchanged_values(self) -> None:
        store = FolderLibraryStore(build_default_preset_folders())
        folder_key = store.create_folder_after("Моя папка", COMMON_FOLDER_KEY)
        current_order = store.to_dict()["folders"][folder_key]["order"]

        self.assertFalse(store.rename_folder(folder_key, "Моя   папка"))
        self.assertFalse(store.move_folder(folder_key, current_order))

    def test_item_metadata_setters_skip_unchanged_values(self) -> None:
        state = build_default_preset_folders()
        state["items"] = {
            "custom.txt": {
                "folder_key": COMMON_FOLDER_KEY,
                "order": 2,
                "rating": 7,
                "pinned": True,
            }
        }
        store = FolderLibraryStore(state)

        self.assertFalse(store.set_item_folder("custom.txt", COMMON_FOLDER_KEY))
        self.assertFalse(store.set_item_order("custom.txt", 2))
        self.assertFalse(store.set_item_rating("custom.txt", 7))
        self.assertFalse(store.set_item_pinned("custom.txt", True))

    def test_default_item_metadata_does_not_create_empty_item(self) -> None:
        store = FolderLibraryStore(build_default_preset_folders())

        self.assertFalse(store.set_item_folder("custom.txt", COMMON_FOLDER_KEY))
        self.assertFalse(store.set_item_order("custom.txt", None))
        self.assertFalse(store.set_item_rating("custom.txt", 0))
        self.assertFalse(store.set_item_pinned("custom.txt", False))
        self.assertEqual(store.to_dict()["items"], {})

    def test_delete_folder_moves_items_to_common(self) -> None:
        store = FolderLibraryStore(build_default_preset_folders())
        folder_key = store.create_folder("Игры")
        store.set_item_folder("custom.txt", folder_key)

        store.delete_folder(folder_key)

        state = store.to_dict()
        self.assertNotIn(folder_key, state["folders"])
        self.assertEqual(state["items"]["custom.txt"]["folder_key"], COMMON_FOLDER_KEY)

    def test_common_folder_cannot_be_deleted_but_can_move(self) -> None:
        store = FolderLibraryStore(build_default_preset_folders())

        self.assertFalse(store.delete_folder(COMMON_FOLDER_KEY))
        self.assertTrue(store.move_folder(COMMON_FOLDER_KEY, 3))
        self.assertEqual(store.to_dict()["folders"][COMMON_FOLDER_KEY]["order"], 3)

    def test_create_folder_after_common_places_user_folder_next_to_common(self) -> None:
        store = FolderLibraryStore(build_default_preset_folders())

        folder_key = store.create_folder_after("Моя папка", COMMON_FOLDER_KEY)

        folders = store.to_dict()["folders"]
        ordered_names = [
            folder["name"]
            for _key, folder in sorted(folders.items(), key=lambda pair: pair[1]["order"])
        ]
        self.assertEqual(folder_key, "моя-папка")
        self.assertEqual(ordered_names, ["ALL TCP & UDP", "Общие", "Моя папка", "1.9.9", "Game filter", "Circular"])

    def test_system_folder_cannot_be_renamed(self) -> None:
        store = FolderLibraryStore(build_default_preset_folders())

        self.assertFalse(store.rename_folder(COMMON_FOLDER_KEY, "Другое имя"))
        self.assertEqual(store.to_dict()["folders"][COMMON_FOLDER_KEY]["name"], "Общие")

    def test_move_folder_by_step_swaps_visible_order(self) -> None:
        store = FolderLibraryStore(build_default_preset_folders())
        folder_key = store.create_folder_after("Моя папка", COMMON_FOLDER_KEY)

        self.assertTrue(store.move_folder_by_step(folder_key, 1))

        ordered_names = [
            folder["name"]
            for _key, folder in sorted(store.to_dict()["folders"].items(), key=lambda pair: pair[1]["order"])
        ]
        self.assertEqual(ordered_names, ["ALL TCP & UDP", "Общие", "1.9.9", "Моя папка", "Game filter", "Circular"])


if __name__ == "__main__":
    unittest.main()
