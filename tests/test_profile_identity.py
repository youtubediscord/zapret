from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.paths import AppPaths
from folders.defaults import classify_profile_folder
from profile.folders import load_profile_folder_state
from profile.identity import (
    generate_profile_uid,
    is_profile_uid,
    normalize_identity_registry,
    resolve_profile_identities,
)
from profile.service import ProfilePresetService


def _uid_factory(prefix: str = "uid:test"):
    counter = {"n": 0}

    def _generate() -> str:
        counter["n"] += 1
        return f"{prefix}-{counter['n']}"

    return _generate


class ProfileIdentityResolverTests(unittest.TestCase):
    def test_exact_match_keeps_uid(self) -> None:
        registry = {"uid:a": {"name": "YouTube", "sig": "sig-yt"}}
        resolution = resolve_profile_identities([("YouTube", "sig-yt")], registry, generate_uid=_uid_factory())
        self.assertEqual(resolution.uids, ("uid:a",))
        self.assertEqual(resolution.new_uids, frozenset())

    def test_rename_matches_by_signature(self) -> None:
        registry = {"uid:a": {"name": "Старое имя", "sig": "sig-1"}}
        resolution = resolve_profile_identities([("Новое имя", "sig-1")], registry, generate_uid=_uid_factory())
        self.assertEqual(resolution.uids, ("uid:a",))
        self.assertEqual(resolution.registry["uid:a"], {"name": "Новое имя", "sig": "sig-1"})

    def test_match_edit_matches_by_name(self) -> None:
        registry = {"uid:a": {"name": "Discord", "sig": "sig-old"}}
        resolution = resolve_profile_identities([("Discord", "sig-new")], registry, generate_uid=_uid_factory())
        self.assertEqual(resolution.uids, ("uid:a",))

    def test_rename_plus_match_edit_creates_new_uid(self) -> None:
        registry = {"uid:a": {"name": "Discord", "sig": "sig-old"}}
        resolution = resolve_profile_identities([("Другое", "sig-new")], registry, generate_uid=_uid_factory())
        self.assertEqual(resolution.uids, ("uid:test-1",))
        self.assertEqual(resolution.new_uids, frozenset({"uid:test-1"}))
        # Несопоставленный uid сохраняется: удалённый и возвращённый профиль
        # снова получает свою мету.
        self.assertIn("uid:a", resolution.registry)

    def test_empty_name_and_sig_bind_only_exactly(self) -> None:
        registry = {"uid:a": {"name": "", "sig": ""}, "uid:b": {"name": "X", "sig": ""}}
        resolution = resolve_profile_identities([("", ""), ("", "sig-1")], registry, generate_uid=_uid_factory())
        # Пустые (name, sig) матчатся только правилом exact; sig-1 ни с кем.
        self.assertEqual(resolution.uids[0], "uid:a")
        self.assertEqual(resolution.uids[1], "uid:test-1")

    def test_duplicates_are_resolved_by_position_deterministically(self) -> None:
        registry = {
            "uid:1": {"name": "Same", "sig": "sig-x"},
            "uid:2": {"name": "Same", "sig": "sig-x"},
        }
        first = resolve_profile_identities([("Same", "sig-x"), ("Same", "sig-x")], registry, generate_uid=_uid_factory())
        second = resolve_profile_identities([("Same", "sig-x"), ("Same", "sig-x")], registry, generate_uid=_uid_factory())
        self.assertEqual(first.uids, second.uids)
        self.assertEqual(set(first.uids), {"uid:1", "uid:2"})

    def test_swap_of_distinct_profiles_does_not_swap_meta(self) -> None:
        registry = {
            "uid:a": {"name": "Alpha", "sig": "sig-a"},
            "uid:b": {"name": "Beta", "sig": "sig-b"},
        }
        resolution = resolve_profile_identities(
            [("Beta", "sig-b"), ("Alpha", "sig-a")], registry, generate_uid=_uid_factory()
        )
        self.assertEqual(resolution.uids, ("uid:b", "uid:a"))

    def test_each_uid_is_used_at_most_once(self) -> None:
        registry = {"uid:a": {"name": "Same", "sig": "sig-1"}}
        resolution = resolve_profile_identities(
            [("Same", "sig-1"), ("Same", "sig-2")], registry, generate_uid=_uid_factory()
        )
        self.assertEqual(resolution.uids[0], "uid:a")
        self.assertTrue(resolution.uids[1].startswith("uid:test"))
        self.assertEqual(len(set(resolution.uids)), 2)

    def test_generated_uid_has_prefix_and_normalization_drops_junk(self) -> None:
        self.assertTrue(is_profile_uid(generate_profile_uid()))
        normalized = normalize_identity_registry({"uid:a": {"name": "X", "sig": "s", "junk": 1}, "": {}, "b": "no"})
        self.assertEqual(normalized, {"uid:a": {"name": "X", "sig": "s"}})


class ClassifyProfileFolderTokenTests(unittest.TestCase):
    def test_word_boundary_prevents_false_positives(self) -> None:
        self.assertNotEqual(classify_profile_folder("wix.com"), "social")
        self.assertNotEqual(classify_profile_folder("fedex.com"), "social")
        self.assertNotEqual(classify_profile_folder("trololo"), "games")
        self.assertNotEqual(classify_profile_folder("snowowl"), "games")

    def test_positive_cases_keep_working(self) -> None:
        self.assertEqual(classify_profile_folder("x.com"), "social")
        self.assertEqual(classify_profile_folder("https://x.com/home"), "social")
        self.assertEqual(classify_profile_folder("vk.com"), "social")
        self.assertEqual(classify_profile_folder("Game filter"), "games")
        self.assertEqual(classify_profile_folder("games"), "games")
        self.assertEqual(classify_profile_folder("steamcommunity.com"), "games")
        self.assertEqual(classify_profile_folder("cdn.discordapp.com"), "discord")
        self.assertEqual(classify_profile_folder("i.ytimg.com youtube"), "youtube")


class _PresetStore:
    def __init__(self, text: str) -> None:
        self.text = text

    def read_selected_preset_source(self, _launch_method: str):
        return self.text, SimpleNamespace(file_name="test.txt", name="test")

    def save_selected_preset_source(self, _launch_method: str, text: str) -> None:
        self.text = text


class ProfileIdentityServiceTests(unittest.TestCase):
    def _service(self, text: str, root: Path) -> tuple[ProfilePresetService, _PresetStore]:
        store = _PresetStore(text)
        feature = SimpleNamespace(
            _presets_feature=store,
            _app_paths=AppPaths(user_root=root, local_root=root),
        )
        return ProfilePresetService(feature, "zapret2_mode"), store

    def test_rename_via_raw_text_keeps_uid_and_folder(self) -> None:
        text = "\n".join(
            (
                "--name=YouTube профиль",
                "--filter-tcp=443",
                "--hostlist=lists/youtube.txt",
                "--lua-desync=pass",
                "",
            )
        )
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "lists").mkdir()
            (root / "lists" / "youtube.txt").write_text("", encoding="utf-8")
            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                service, _store = self._service(text, root)
                preset, _manifest = service.load_selected_preset()
                uid = preset.profiles[0].persistent_key
                self.assertTrue(is_profile_uid(uid))
                # Первичное размещение материализовано.
                state = load_profile_folder_state()
                self.assertEqual(state["items"][uid]["folder_key"], "youtube")

                result = service.update_profile_raw_text(
                    uid,
                    "\n".join(
                        (
                            "--name=Совсем другое имя",
                            "--filter-tcp=443",
                            "--hostlist=lists/youtube.txt",
                            "--lua-desync=pass",
                        )
                    ),
                )
                self.assertEqual(result, (uid, uid))
                # Папка не «уплыла»: мета осталась на том же uid.
                state = load_profile_folder_state()
                self.assertEqual(state["items"][uid]["folder_key"], "youtube")

    def test_unnamed_profile_match_edit_keeps_uid(self) -> None:
        text = "\n".join(("--filter-tcp=443", "--lua-desync=pass", ""))
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                service, _store = self._service(text, root)
                preset, _manifest = service.load_selected_preset()
                uid = preset.profiles[0].persistent_key
                self.assertTrue(is_profile_uid(uid))

                # Правка match-строк безымянного профиля меняет сигнатуру;
                # сервис обязан закрепить новый контент за прежним uid.
                result = service.update_profile_raw_text(
                    uid,
                    "\n".join(("--filter-tcp=80,443", "--lua-desync=pass")),
                )
                self.assertEqual(result, (uid, uid))

    def test_classification_change_does_not_move_profile_after_first_placement(self) -> None:
        text = "\n".join(("--name=Просто профиль", "--filter-tcp=443", "--lua-desync=pass", ""))
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                service, _store = self._service(text, root)
                preset, _manifest = service.load_selected_preset()
                uid = preset.profiles[0].persistent_key
                state = load_profile_folder_state()
                self.assertEqual(state["items"][uid]["folder_key"], "common")

                # Теперь текст профиля «выглядит как Discord», но размещение
                # первично и не пересчитывается.
                result = service.update_profile_raw_text(
                    uid,
                    "\n".join(("--name=Просто профиль", "--filter-tcp=443", "--hostlist=lists/discord.txt", "--lua-desync=pass")),
                )
                self.assertEqual(result, (uid, uid))
                state = load_profile_folder_state()
                self.assertEqual(state["items"][uid]["folder_key"], "common")


if __name__ == "__main__":
    unittest.main()
