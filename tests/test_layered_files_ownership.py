"""Ownership-архитектура layered_files: чистый планировщик и защита EXTERNAL.

Спека: .agent/tasks/fix-list-editor-crumbs/spec.md (AC6, AC7).
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from lists.core.layered_files import (
    ListOwnership,
    _LayerSnapshot,
    _plan_rebuild,
    create_profile_user_list_file,
    delete_profile_user_list_file,
    rebuild_all_layered_list_files,
    rebuild_profile_list_file,
    rename_profile_user_list_file,
    write_profile_user_list_text,
)


def _snapshot(
    *,
    base_exists: bool = False,
    user_exists: bool = False,
    base_entries: tuple[str, ...] = (),
    user_entries: tuple[str, ...] = (),
    user_text: str = "",
    final_entries: tuple[str, ...] = (),
) -> _LayerSnapshot:
    return _LayerSnapshot(
        base_exists=base_exists,
        user_exists=user_exists,
        base_entries=base_entries,
        user_entries=user_entries,
        user_text=user_text,
        final_entries=final_entries,
    )


class ListOwnershipTableTests(unittest.TestCase):
    def test_ownership_table(self) -> None:
        cases = [
            # (описание, snapshot, ожидаемое владение)
            (
                "base с записями",
                _snapshot(base_exists=True, base_entries=("a.com",)),
                ListOwnership.LAYERED,
            ),
            (
                "user с записями, базы нет",
                _snapshot(user_exists=True, user_entries=("a.com",), user_text="a.com\n"),
                ListOwnership.LAYERED,
            ),
            (
                "слоёв нет, итог с реальными записями (скачанный список)",
                _snapshot(final_entries=("1.2.3.0/24",)),
                ListOwnership.EXTERNAL,
            ),
            (
                "пустая user-крошка, итог с реальными записями",
                _snapshot(user_exists=True, final_entries=("1.2.3.0/24",)),
                ListOwnership.EXTERNAL,
            ),
            (
                "пустая base-крошка, итог с реальными записями",
                _snapshot(base_exists=True, final_entries=("1.2.3.0/24",)),
                ListOwnership.EXTERNAL,
            ),
            (
                "слои только с комментариями, итог с реальными записями",
                _snapshot(
                    user_exists=True,
                    user_entries=("# note",),
                    user_text="# note\n",
                    final_entries=("1.2.3.0/24",),
                ),
                ListOwnership.EXTERNAL,
            ),
            (
                "пустые base+user, итога нет — слои владеют (плейсхолдер)",
                _snapshot(base_exists=True, user_exists=True),
                ListOwnership.LAYERED,
            ),
            (
                "итог только с комментариями, слоёв нет",
                _snapshot(final_entries=("# stale",)),
                ListOwnership.ABSENT,
            ),
            (
                "ничего нет",
                _snapshot(),
                ListOwnership.ABSENT,
            ),
        ]
        for description, snapshot, expected in cases:
            with self.subTest(description):
                self.assertIs(snapshot.ownership, expected)


class PlanRebuildTableTests(unittest.TestCase):
    def test_background_plan_is_noop_for_external_final(self) -> None:
        for description, snapshot in [
            ("слоёв нет вовсе", _snapshot(final_entries=("1.2.3.0/24",))),
            ("пустая user-крошка", _snapshot(user_exists=True, final_entries=("1.2.3.0/24",))),
            ("пустая base-крошка", _snapshot(base_exists=True, final_entries=("1.2.3.0/24",))),
        ]:
            with self.subTest(description):
                plan = _plan_rebuild("ipset-ru.txt", snapshot, authoritative=False)
                self.assertIsNone(plan.write_user)
                self.assertIsNone(plan.write_final)
                self.assertFalse(plan.unlink_final)

    def test_authoritative_plan_overrides_external_final(self) -> None:
        # Явная очистка user-слоя: слои — источник истины, финал пересеивается
        # плейсхолдером даже поверх внешнего содержимого.
        snapshot = _snapshot(user_exists=True, final_entries=("1.2.3.0/24",))
        plan = _plan_rebuild("ipset-ru.txt", snapshot, authoritative=True)
        self.assertEqual(plan.write_user, "123.123.123.123")
        self.assertEqual(plan.write_final, "123.123.123.123\n")
        self.assertFalse(plan.unlink_final)

    def test_authoritative_plan_unlinks_final_without_layers(self) -> None:
        # Удаление списка: user-слой уже снят, итог обязан исчезнуть.
        snapshot = _snapshot(final_entries=("qwen.ai",))
        plan = _plan_rebuild("custom.txt", snapshot, authoritative=True)
        self.assertTrue(plan.unlink_final)
        self.assertIsNone(plan.write_user)

    def test_layered_plan_combines_layers(self) -> None:
        snapshot = _snapshot(
            base_exists=True,
            user_exists=True,
            base_entries=("base.com",),
            user_entries=("user.com",),
            user_text="user.com\n",
        )
        for authoritative in (False, True):
            with self.subTest(authoritative=authoritative):
                plan = _plan_rebuild("youtube.txt", snapshot, authoritative=authoritative)
                self.assertIsNone(plan.write_user)
                self.assertEqual(plan.write_final, "base.com\nuser.com\n")

    def test_layered_plan_seeds_placeholder_for_empty_layers(self) -> None:
        # Существующий пустой список (например, только комментарии) обязан
        # остаться валидным для winws — сеется безопасный плейсхолдер.
        snapshot = _snapshot(
            base_exists=True,
            user_exists=True,
            user_entries=("# note",),
            user_text="# note\n",
        )
        plan = _plan_rebuild("empty.txt", snapshot, authoritative=False)
        self.assertEqual(plan.write_user, "# note\nwww.example.com")
        self.assertEqual(plan.write_final, "# note\nwww.example.com\n")

    def test_absent_plan_unlinks_stale_final(self) -> None:
        snapshot = _snapshot(final_entries=("# stale",))
        plan = _plan_rebuild("custom.txt", snapshot, authoritative=False)
        self.assertTrue(plan.unlink_final)


class ExternalFinalProtectionTests(unittest.TestCase):
    def test_rebuild_all_keeps_external_final_intact(self) -> None:
        # Стартовая пересборка (rebuild_all + пустая user-крошка от старой
        # версии) не должна затирать скачанный lists/ipset-ru.txt.
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "user").mkdir(parents=True)
            (lists_dir / "ipset-ru.txt").write_text("1.2.3.0/24\n5.6.7.0/24\n", encoding="utf-8")
            (lists_dir / "user" / "ipset-ru.txt").write_text("", encoding="utf-8")

            rebuilt = rebuild_all_layered_list_files(lists_dir, user_only_file_names={"ipset-ru.txt"})

            self.assertEqual(rebuilt, 1)
            self.assertEqual(
                (lists_dir / "ipset-ru.txt").read_text(encoding="utf-8"),
                "1.2.3.0/24\n5.6.7.0/24\n",
            )
            self.assertEqual(
                (lists_dir / "user" / "ipset-ru.txt").read_text(encoding="utf-8"),
                "",
            )

    def test_create_keeps_external_final_intact(self) -> None:
        # Создание user-слоя (новый список) — не повод затирать внешний итог:
        # содержимое утверждается первым сохранением.
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            lists_dir.mkdir(parents=True)
            (lists_dir / "ipset-ru.txt").write_text("1.2.3.0/24\n", encoding="utf-8")

            create_profile_user_list_file(lists_dir, "ipset-ru.txt")

            self.assertEqual(
                (lists_dir / "ipset-ru.txt").read_text(encoding="utf-8"),
                "1.2.3.0/24\n",
            )
            self.assertEqual(
                (lists_dir / "user" / "ipset-ru.txt").read_text(encoding="utf-8"),
                "",
            )

    def test_create_seeds_placeholder_for_fresh_list(self) -> None:
        # Для нового имени без внешнего итога create ведёт себя как раньше:
        # пустой список материализуется плейсхолдером (winws не падает).
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"

            paths = create_profile_user_list_file(lists_dir, "ipset-fresh.txt")

            self.assertEqual(
                paths.user_path.read_text(encoding="utf-8"),
                "123.123.123.123\n",
            )
            self.assertEqual(
                paths.final_path.read_text(encoding="utf-8"),
                "123.123.123.123\n",
            )

    def test_rename_onto_external_final_keeps_it_intact(self) -> None:
        # Перенос пустого user-слоя на имя скачанного списка не затирает итог.
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "user").mkdir(parents=True)
            (lists_dir / "user" / "old.txt").write_text("", encoding="utf-8")
            (lists_dir / "ipset-ru.txt").write_text("1.2.3.0/24\n", encoding="utf-8")

            rename_profile_user_list_file(lists_dir, "old.txt", "ipset-ru.txt")

            self.assertEqual(
                (lists_dir / "ipset-ru.txt").read_text(encoding="utf-8"),
                "1.2.3.0/24\n",
            )
            self.assertFalse((lists_dir / "old.txt").exists())

    def test_explicit_save_takes_ownership_of_external_final(self) -> None:
        # Сохранение текста в редакторе — авторитетно: слои забирают владение.
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            lists_dir.mkdir(parents=True)
            (lists_dir / "ipset-ru.txt").write_text("1.2.3.0/24\n", encoding="utf-8")

            write_profile_user_list_text(lists_dir, "ipset-ru.txt", "9.9.9.9\n")

            self.assertEqual(
                (lists_dir / "ipset-ru.txt").read_text(encoding="utf-8"),
                "9.9.9.9\n",
            )

    def test_delete_keeps_external_final_intact(self) -> None:
        # Пользователь создал список с именем поставляемого файла (пустая
        # user-крошка) и удалил профиль: итог установщика обязан уцелеть.
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "user").mkdir(parents=True)
            (lists_dir / "user" / "discord-images.txt").write_text("", encoding="utf-8")
            (lists_dir / "discord-images.txt").write_text("media.discordapp.net\n", encoding="utf-8")

            delete_profile_user_list_file(lists_dir, "discord-images.txt")

            self.assertEqual(
                (lists_dir / "discord-images.txt").read_text(encoding="utf-8"),
                "media.discordapp.net\n",
            )
            self.assertFalse((lists_dir / "user" / "discord-images.txt").exists())

    def test_rename_away_from_external_final_keeps_it_intact(self) -> None:
        # Переименование профиля, чья пустая user-крошка носила имя
        # поставляемого списка: старый итог остаётся, крошка переезжает.
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "user").mkdir(parents=True)
            (lists_dir / "user" / "discord-images.txt").write_text("", encoding="utf-8")
            (lists_dir / "discord-images.txt").write_text("media.discordapp.net\n", encoding="utf-8")

            rename_profile_user_list_file(lists_dir, "discord-images.txt", "custom.txt")

            self.assertEqual(
                (lists_dir / "discord-images.txt").read_text(encoding="utf-8"),
                "media.discordapp.net\n",
            )
            self.assertFalse((lists_dir / "user" / "discord-images.txt").exists())
            self.assertTrue((lists_dir / "user" / "custom.txt").is_file())

    def test_rename_away_from_layered_final_removes_stale_final(self) -> None:
        # Старое поведение для user-owned списка не сломано: унесённый
        # user-слой забирает с собой протухший итог.
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "user").mkdir(parents=True)
            (lists_dir / "user" / "custom.txt").write_text("qwen.ai\n", encoding="utf-8")
            rebuild_profile_list_file(lists_dir, "custom.txt")
            self.assertTrue((lists_dir / "custom.txt").is_file())

            rename_profile_user_list_file(lists_dir, "custom.txt", "renamed.txt")

            self.assertFalse((lists_dir / "custom.txt").exists())
            self.assertEqual(
                (lists_dir / "renamed.txt").read_text(encoding="utf-8"),
                "qwen.ai\n",
            )

    def test_delete_unlinks_final_without_base(self) -> None:
        # Удаление user-only списка обязано убрать итог (авторитетный unlink).
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "user").mkdir(parents=True)
            (lists_dir / "user" / "custom.txt").write_text("qwen.ai\n", encoding="utf-8")
            rebuild_profile_list_file(lists_dir, "custom.txt")
            self.assertTrue((lists_dir / "custom.txt").is_file())

            delete_profile_user_list_file(lists_dir, "custom.txt")

            self.assertFalse((lists_dir / "custom.txt").exists())
            self.assertFalse((lists_dir / "user" / "custom.txt").exists())


if __name__ == "__main__":
    unittest.main()
