from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from core.paths import AppPaths
from profile.key_resolution import profile_reference_key
from profile.parser import parse_preset_text
from profile.service import ProfilePresetService


THREE_PROFILES = """--name=Alpha
--filter-tcp=80
--hostlist=lists/alpha.txt
--lua-desync=pass

--new
--name=Beta
--filter-tcp=443
--hostlist=lists/beta.txt
--lua-desync=pass

--new
--name=Gamma
--filter-udp=443
--hostlist=lists/gamma.txt
--lua-desync=pass
"""

DUPLICATE_NAMES = """--name=YouTube
--filter-tcp=80,443
--hostlist=lists/youtube.txt
--lua-desync=pass

--new
--name=YouTube
--filter-tcp=80,443
--ipset=lists/ipset-youtube.txt
--lua-desync=pass

--new
--name=YouTube
--filter-tcp=80,443
--ipset=lists/ipset-youtube.txt
--lua-desync=pass
"""


class _PresetStore:
    def __init__(self, text: str = "") -> None:
        self.text = text

    def read_selected_preset_source(self, _launch_method: str):
        return self.text, SimpleNamespace(file_name="selected.txt", name="selected")

    def save_selected_preset_source(self, _launch_method: str, text: str) -> None:
        self.text = text


class PersistentKeyUniquenessTests(unittest.TestCase):
    def test_duplicate_names_get_unique_persistent_keys(self) -> None:
        preset = parse_preset_text(DUPLICATE_NAMES, engine="winws2")
        keys = [profile.persistent_key for profile in preset.profiles]
        self.assertEqual(len(keys), len(set(keys)))

    def test_first_duplicate_keeps_base_key_for_saved_meta_compat(self) -> None:
        preset = parse_preset_text(DUPLICATE_NAMES, engine="winws2")
        self.assertEqual(preset.profiles[0].persistent_key, "name:YouTube")
        for profile in preset.profiles[1:]:
            self.assertTrue(profile.persistent_key.startswith("name:YouTube|"))

    def test_unique_names_are_untouched_by_dedup(self) -> None:
        preset = parse_preset_text(THREE_PROFILES, engine="winws2")
        self.assertEqual(
            [profile.persistent_key for profile in preset.profiles],
            ["name:Alpha", "name:Beta", "name:Gamma"],
        )

    def test_duplicate_base_key_owner_is_stable_across_reorder(self) -> None:
        """Регресс: владелец базового ключа выбирается по контенту, поэтому
        перестановка одноимённой пары не переносит мету/ссылки между ними."""
        pair = (
            "--name=YouTube\n--filter-tcp=443\n--hostlist=lists/youtube.txt\n--lua-desync=pass\n",
            "--new\n--name=YouTube\n--filter-udp=443\n--ipset=lists/ipset-youtube.txt\n--lua-desync=pass\n",
        )
        direct = parse_preset_text("\n".join(pair), engine="winws2")
        swapped = parse_preset_text(
            "\n".join((pair[1].removeprefix("--new\n"), "--new\n" + pair[0])),
            engine="winws2",
        )

        def keys_by_filter(preset):
            return {
                ("udp" if any("udp" in line for line in profile.match.filter_lines) else "tcp"):
                profile.persistent_key
                for profile in preset.profiles
            }

        self.assertEqual(keys_by_filter(direct), keys_by_filter(swapped))

    def test_persistent_keys_survive_reorder(self) -> None:
        preset = parse_preset_text(THREE_PROFILES, engine="winws2")
        original = {profile.name: profile.persistent_key for profile in preset.profiles}
        reordered_text = "\n".join(
            (
                "--name=Gamma",
                "--filter-udp=443",
                "--hostlist=lists/gamma.txt",
                "--lua-desync=pass",
                "",
                "--new",
                "--name=Alpha",
                "--filter-tcp=80",
                "--hostlist=lists/alpha.txt",
                "--lua-desync=pass",
                "",
                "--new",
                "--name=Beta",
                "--filter-tcp=443",
                "--hostlist=lists/beta.txt",
                "--lua-desync=pass",
                "",
            )
        )
        reordered = parse_preset_text(reordered_text, engine="winws2")
        self.assertEqual(
            {profile.name: profile.persistent_key for profile in reordered.profiles},
            original,
        )


class ProfileReferenceKeyTests(unittest.TestCase):
    def test_preset_item_reference_is_persistent_key(self) -> None:
        item = SimpleNamespace(in_preset=True, key="profile:2", persistent_key="name:Beta")
        self.assertEqual(profile_reference_key(item), "name:Beta")

    def test_template_item_reference_is_template_key(self) -> None:
        item = SimpleNamespace(in_preset=False, key="template:user:my-site", persistent_key="")
        self.assertEqual(profile_reference_key(item), "template:user:my-site")


class StaleReferenceCorrectnessTests(unittest.TestCase):
    def _make_service(self, root: Path, text: str) -> tuple[ProfilePresetService, _PresetStore]:
        (root / "profile" / "templates").mkdir(parents=True, exist_ok=True)
        (root / "profile" / "templates" / "all_profiles.txt").write_text("", encoding="utf-8")
        store = _PresetStore(text)
        feature = SimpleNamespace(
            _presets_feature=store,
            _app_paths=AppPaths(user_root=root, local_root=root),
        )
        return ProfilePresetService(feature, "zapret2_mode"), store

    def test_persistent_reference_targets_correct_profile_after_neighbor_delete(self) -> None:
        """Регресс: устаревший "profile:2" после удаления соседа резолвится в чужой
        профиль; persistent-ссылка обязана попадать в исходный."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service, store = self._make_service(root, THREE_PROFILES)

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                payload = service.list_profiles()
                gamma_item = next(
                    item for item in payload.items
                    if getattr(item, "display_name", "") == "Gamma"
                )
                gamma_reference = profile_reference_key(gamma_item)
                # Идентичность стабильна: ссылка — uid из sidecar-реестра.
                self.assertTrue(gamma_reference.startswith("uid:"))

                # Сосед удалён из другого места — позиционные ключи сдвинулись.
                self.assertTrue(service.delete_profile("profile:0"))

                new_key = service.update_profile_raw_text(
                    gamma_reference,
                    "--name=Gamma\n--filter-udp=443\n--hostlist=lists/gamma.txt\n--lua-desync=fake",
                )

        self.assertIsNotNone(new_key)
        preset = parse_preset_text(store.text, engine="winws2")
        by_name = {profile.name: profile for profile in preset.profiles}
        self.assertNotIn("Alpha", by_name)
        gamma_lines = [segment.text for segment in by_name["Gamma"].segments]
        beta_lines = [segment.text for segment in by_name["Beta"].segments]
        self.assertIn("--lua-desync=fake", gamma_lines)
        self.assertNotIn("--lua-desync=fake", beta_lines)

    def test_queued_deletes_by_reference_target_correct_profiles(self) -> None:
        """Регресс бага очереди: два быстрых удаления. Ключи захвачены до сдвига
        индексов; позиционные ключи удалили бы чужой профиль (после удаления
        Alpha ключ "profile:2" указывает уже не на Gamma)."""
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service, store = self._make_service(root, THREE_PROFILES)

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                payload = service.list_profiles()
                references = {
                    getattr(item, "display_name", ""): profile_reference_key(item)
                    for item in payload.items
                }
                # Обе ссылки захвачены заранее — как при быстрых кликах в UI.
                self.assertTrue(service.delete_profile(references["Alpha"]))
                self.assertTrue(service.delete_profile(references["Gamma"]))

        preset = parse_preset_text(store.text, engine="winws2")
        self.assertEqual([profile.name for profile in preset.profiles], ["Beta"])

    def test_list_items_expose_reference_resolvable_by_service(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            service, _store = self._make_service(root, THREE_PROFILES)

            with patch("settings.store.MAIN_DIRECTORY", str(root)):
                payload = service.list_profiles()
                for item in payload.items:
                    reference = profile_reference_key(item)
                    setup = service.get_profile_setup(reference)
                    self.assertIsNotNone(setup, f"reference {reference} не резолвится")
                    self.assertEqual(
                        getattr(setup.item, "persistent_key", ""),
                        getattr(item, "persistent_key", ""),
                    )


if __name__ == "__main__":
    unittest.main()
