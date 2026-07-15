"""Инварианты единого источника истины порядка профилей (profile-order-single-source).

AC1: показанный после перемещения порядок == порядку после перечитывания
     сохранённого состояния (регрессия «папки прыгают»).
AC2: no-op определяется по отображаемому порядку, а не по порядку файла пресета.
AC3: план не трогает элементы других папок и не переписывает их folder_key.
AC4: порядок заголовков папок берётся из сохранённого состояния (кастомные
     папки участвуют наравне со стандартными).
"""
from __future__ import annotations

import unittest

from folders.defaults import build_default_profile_folders
from profile.display_items import ProfileDisplayItem
from profile.list_view_state import (
    apply_profile_folder_state_to_items,
    grouped_items,
    moved_profile_display_items,
    ordered_group_keys,
)
from profile.ordering import (
    live_items_from_display_items,
    plan_profile_move,
    resolve_profile_order_view,
)


def _item(
    key: str,
    name: str,
    *,
    match_lines: tuple[str, ...],
    source_order: int,
    group: str = "common",
    group_name: str = "Общие",
    order: int = 0,
    group_rank: int = 10_000,
) -> ProfileDisplayItem:
    return ProfileDisplayItem(
        key=key,
        persistent_key=key,
        profile_index=source_order,
        display_name=name,
        enabled=True,
        in_preset=True,
        strategy_id="none",
        strategy_name="Стратегия не выбрана",
        match_lines=match_lines,
        list_type="hostlist",
        rating="",
        favorite=False,
        group=group,
        group_name=group_name,
        order=order,
        source_order=source_order,
        group_rank=group_rank,
    )


def _youtube_items() -> tuple[ProfileDisplayItem, ...]:
    return (
        _item("yt-ui", "youtube.com (интерфейс)", match_lines=("--filter-tcp=80,443",), source_order=0),
        _item("yt-quic", "youtube.com (QUIC)", match_lines=("--filter-udp=443",), source_order=1),
        _item("googlevideo", "googlevideo.com (CDN серверы)", match_lines=("--filter-tcp=80,443",), source_order=2),
        _item("yt-rtmps", "youtube.com (RTMPS)", match_lines=("--filter-tcp=443",), source_order=3),
    )


def _youtube_state() -> dict:
    state = build_default_profile_folders()
    state["items"] = {
        "yt-ui": {"folder_key": "youtube", "order": 0, "rating": 0},
        "yt-quic": {"folder_key": "youtube", "order": 1, "rating": 0},
    }
    return state


class ProfileOrderRoundTripTests(unittest.TestCase):
    def test_display_order_mixes_manual_first_then_protocol(self) -> None:
        view = resolve_profile_order_view(live_items_from_display_items(_youtube_items()), _youtube_state())

        # Ручной порядок первым (yt-ui, yt-quic), затем авто по протоколу:
        # TCP-профили googlevideo (index 2) и rtmps (index 3).
        self.assertEqual(
            view.items_by_folder["youtube"],
            ("yt-ui", "yt-quic", "googlevideo", "yt-rtmps"),
        )

    def test_vencord_is_last_in_discord_default_order(self) -> None:
        items = (
            _item("discord-tcp", "discord.com", match_lines=("--filter-tcp=443",), source_order=0),
            _item("discord-udp", "Discord UDP", match_lines=("--filter-udp=443-65535",), source_order=1),
            _item("discord-voice", "Discord voice", match_lines=("--filter-l7=stun,discord",), source_order=2),
            _item(
                "vencord",
                "vencord.dev",
                match_lines=("--filter-tcp=80,443", "--hostlist=lists/vencord.txt"),
                source_order=3,
            ),
        )

        view = resolve_profile_order_view(
            live_items_from_display_items(items),
            build_default_profile_folders(),
        )

        self.assertEqual(
            view.items_by_folder["discord"],
            ("discord-tcp", "discord-udp", "discord-voice", "vencord"),
        )

    def test_ac1_move_round_trip_matches_optimistic_order(self) -> None:
        items = _youtube_items()
        state = _youtube_state()
        live = live_items_from_display_items(items)

        planned = plan_profile_move(
            live,
            state,
            action="before",
            source_key="googlevideo",
            destination_key="yt-quic",
        )
        self.assertIsNotNone(planned)

        # Персист: перечитываем состояние тем же резолвером.
        persisted_view = resolve_profile_order_view(live, planned)
        # Оптимистичный UI: тот же ход по УЖЕ разрешённым item-ам (модель
        # всегда держит их в каноническом виде).
        resolved_items = apply_profile_folder_state_to_items(items, state)
        optimistic = moved_profile_display_items(resolved_items, "googlevideo", "profile", "yt-quic")
        self.assertIsNotNone(optimistic)
        optimistic_youtube = [
            item.key
            for item in sorted(
                (item for item in optimistic if item.group == "youtube"),
                key=lambda item: item.order,
            )
        ]

        expected = ["yt-ui", "googlevideo", "yt-quic", "yt-rtmps"]
        self.assertEqual(list(persisted_view.items_by_folder["youtube"]), expected)
        self.assertEqual(optimistic_youtube, expected)

        # Повторная перестройка из сохранённого состояния не меняет порядок.
        reapplied = apply_profile_folder_state_to_items(items, planned)
        reapplied_youtube = [item.key for item in reapplied if item.group == "youtube"]
        self.assertEqual(reapplied_youtube, expected)

    def test_ac1_ui_optimistic_equals_persisted_rebuild(self) -> None:
        items = _youtube_items()
        state = _youtube_state()

        resolved_items = apply_profile_folder_state_to_items(items, state)
        optimistic = moved_profile_display_items(resolved_items, "yt-rtmps", "profile_after", "yt-ui")
        planned = plan_profile_move(
            live_items_from_display_items(items),
            state,
            action="after",
            source_key="yt-rtmps",
            destination_key="yt-ui",
        )
        self.assertIsNotNone(optimistic)
        self.assertIsNotNone(planned)

        optimistic_order = [
            item.key
            for item in sorted(
                (item for item in optimistic if item.group == "youtube"),
                key=lambda item: item.order,
            )
        ]
        rebuilt = apply_profile_folder_state_to_items(items, planned)
        rebuilt_order = [item.key for item in rebuilt if item.group == "youtube"]
        self.assertEqual(optimistic_order, rebuilt_order)


class ProfileOrderNoOpTests(unittest.TestCase):
    def _abc_state(self) -> tuple[list[dict], dict]:
        items = (
            _item("a", "site a", match_lines=("--filter-tcp=443",), source_order=0),
            _item("b", "site b", match_lines=("--filter-tcp=443",), source_order=1),
            _item("c", "site c", match_lines=("--filter-tcp=443",), source_order=2),
        )
        state = build_default_profile_folders()
        # Отображаемый порядок: b, c, a — намеренно отличается от файла (a, b, c).
        state["items"] = {
            "a": {"folder_key": "common", "order": 2, "rating": 0},
            "b": {"folder_key": "common", "order": 0, "rating": 0},
            "c": {"folder_key": "common", "order": 1, "rating": 0},
        }
        return live_items_from_display_items(items), state

    def test_ac2_move_changing_display_order_is_saved_even_if_file_order_matches(self) -> None:
        live, state = self._abc_state()
        # В файле «a прямо перед b» — старый код молча отбрасывал такой ход.
        planned = plan_profile_move(live, state, action="before", source_key="a", destination_key="b")
        self.assertIsNotNone(planned)
        view = resolve_profile_order_view(live, planned)
        self.assertEqual(view.items_by_folder["common"], ("a", "b", "c"))

    def test_ac2_move_not_changing_display_order_is_noop(self) -> None:
        live, state = self._abc_state()
        # b и так прямо перед c на экране.
        self.assertIsNone(plan_profile_move(live, state, action="before", source_key="b", destination_key="c"))
        # a и так последний — move-to-end не сохраняется.
        self.assertIsNone(plan_profile_move(live, state, action="end", source_key="a"))


class ProfileOrderStateHygieneTests(unittest.TestCase):
    def test_ac3_move_does_not_touch_other_folders(self) -> None:
        items = (
            *_youtube_items(),
            _item("dis-1", "discord.com", match_lines=("--filter-tcp=443",), source_order=4),
            _item("plain", "example site", match_lines=("--filter-tcp=443",), source_order=5),
        )
        state = _youtube_state()
        state["items"]["dis-1"] = {"folder_key": "discord", "order": 5, "rating": 3}
        before_discord = dict(state["items"]["dis-1"])

        planned = plan_profile_move(
            live_items_from_display_items(items),
            state,
            action="before",
            source_key="googlevideo",
            destination_key="yt-ui",
        )
        self.assertIsNotNone(planned)

        # Meta другой папки не изменилась ни на бит.
        self.assertEqual(planned["items"]["dis-1"], before_discord)
        # Профиль вне затронутой папки не получил новую meta.
        self.assertNotIn("plain", planned["items"])
        # folder_key участников целевой папки — только их отображаемая папка.
        for key in ("yt-ui", "yt-quic", "googlevideo", "yt-rtmps"):
            self.assertEqual(planned["items"][key]["folder_key"], "youtube")


class FolderHeaderOrderTests(unittest.TestCase):
    def test_ac4_headers_follow_saved_folder_order_including_custom(self) -> None:
        state = build_default_profile_folders()
        # Кастомная папка, переставленная пользователем на самый верх.
        for folder in state["folders"].values():
            folder["order"] = int(folder["order"]) + 1
        state["folders"]["myfolder"] = {"name": "Моя папка", "order": 0, "collapsed": False, "system": False}
        state["items"] = {
            "custom-1": {"folder_key": "myfolder", "order": 0, "rating": 0},
            "yt-ui": {"folder_key": "youtube", "order": 0, "rating": 0},
        }
        items = (
            _item("yt-ui", "youtube.com (интерфейс)", match_lines=("--filter-tcp=80,443",), source_order=0),
            _item("custom-1", "custom profile", match_lines=("--filter-tcp=443",), source_order=1),
        )

        applied = apply_profile_folder_state_to_items(items, state)
        keys = ordered_group_keys(grouped_items(applied))
        self.assertLess(keys.index("myfolder"), keys.index("youtube"))


class CrossFolderMoveTests(unittest.TestCase):
    def test_move_to_folder_appends_to_target_and_leaves_source_folder_gap_intact(self) -> None:
        items = (
            *_youtube_items(),
            _item("dis-1", "discord.com", match_lines=("--filter-tcp=443",), source_order=4),
        )
        state = _youtube_state()
        state["items"]["dis-1"] = {"folder_key": "discord", "order": 0, "rating": 0}
        live = live_items_from_display_items(items)

        planned = plan_profile_move(live, state, action="folder", source_key="yt-quic", destination_folder_key="discord")
        self.assertIsNotNone(planned)
        view = resolve_profile_order_view(live, planned)
        self.assertEqual(view.items_by_folder["discord"], ("dis-1", "yt-quic"))
        # Оставшиеся в youtube сохраняют относительный порядок.
        self.assertEqual(view.items_by_folder["youtube"], ("yt-ui", "googlevideo", "yt-rtmps"))


if __name__ == "__main__":
    unittest.main()
