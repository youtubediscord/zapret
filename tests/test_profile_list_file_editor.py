from __future__ import annotations

import threading
import time
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest

from core.paths import AppPaths
from profile.list_file_editor import (
    count_profile_list_entries,
    profile_list_file_reference,
    validate_profile_list_file_text,
)
from lists.core.layered_files import rebuild_all_layered_list_files, rebuild_profile_list_file
from profile.parser import parse_preset_text
from profile.service import ProfilePresetService
from settings.mode import ENGINE_WINWS2


class _PresetStore:
    def __init__(self, text: str) -> None:
        self.text = text

    def read_selected_preset_source(self, _launch_method: str):
        return self.text, SimpleNamespace(file_name="selected.txt", name="selected")

    def save_selected_preset_source(self, _launch_method: str, text: str) -> None:
        self.text = text


class ProfileListFileEditorTests(unittest.TestCase):
    def test_validates_hostlist_domains(self) -> None:
        invalid = validate_profile_list_file_text(
            "hostlist",
            "youtube.com\nbad domain\n# comment\nsub.example.org\n",
        )

        self.assertEqual(invalid, ((2, "bad domain"),))

    def test_hostlist_rejects_ip_addresses(self) -> None:
        invalid = validate_profile_list_file_text(
            "hostlist",
            "chatgpt.com\n1.2.3.4\n012.34.56.78\n2a00:1450::1\n8.8.8.8\n",
        )

        self.assertEqual(
            invalid,
            (
                (2, "1.2.3.4"),
                (3, "012.34.56.78"),
                (4, "2a00:1450::1"),
                (5, "8.8.8.8"),
            ),
        )

    def test_hostlist_accepts_domains_with_digit_labels(self) -> None:
        invalid = validate_profile_list_file_text(
            "hostlist",
            "123movies.example\n4chan.org\nchatgpt.com\n1.fdn.fr\n",
        )

        self.assertEqual(invalid, ())

    def test_validates_ipset_entries(self) -> None:
        invalid = validate_profile_list_file_text(
            "ipset",
            "1.1.1.1\n10.0.0.0/8\ndiscord.com\n1.1.1.1-2.2.2.2\n",
        )

        self.assertEqual(invalid, ((3, "discord.com"), (4, "1.1.1.1-2.2.2.2")))

    def test_counts_list_entries_without_comments(self) -> None:
        count = count_profile_list_entries(
            "youtube.com\n# comment\n\nsub.example.org\n",
        )

        self.assertEqual(count, 2)

    def test_profile_reference_uses_current_hostlist_file(self) -> None:
        preset = parse_preset_text(
            "--filter-tcp=80,443\n--hostlist=lists/youtube.txt\n--lua-desync=pass\n",
            engine=ENGINE_WINWS2,
        )

        reference = profile_list_file_reference(preset.profiles[0], Path("/tmp/lists"))

        self.assertTrue(reference.editable)
        self.assertEqual(reference.kind, "hostlist")
        self.assertEqual(reference.file_name, "youtube.txt")

    def test_l7_voice_profile_has_no_editable_list_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / "lists").mkdir()
            store = _PresetStore(
                "--filter-l7=stun,discord\n"
                "--payload=stun,discord_ip_discovery\n"
                "--lua-desync=pass\n"
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            setup = service.get_profile_setup("profile:0")
            list_editor = service.get_profile_list_file_editor_state("profile:0")

            self.assertIsNotNone(setup)
            self.assertIsNotNone(list_editor)
            self.assertFalse(setup.editable_filter_enabled)
            self.assertEqual(setup.editable_filter_value, "")
            self.assertFalse(list_editor.editable)
            self.assertIn("нет отдельного hostlist/ipset-файла", list_editor.error_text)

    def test_service_loads_and_saves_current_profile_list_file(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "user").mkdir()
            (lists_dir / "base" / "ipset-youtube.txt").write_text("1.1.1.1\n", encoding="utf-8")
            (lists_dir / "user" / "ipset-youtube.txt").write_text("2.2.2.2\n", encoding="utf-8")
            store = _PresetStore(
                "--filter-tcp=80,443\n--ipset=lists/ipset-youtube.txt\n--lua-desync=pass\n"
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            setup = service.get_profile_setup("profile:0")
            list_editor = service.get_profile_list_file_editor_state("profile:0")
            self.assertIsNotNone(setup)
            self.assertIsNotNone(list_editor)
            self.assertEqual(list_editor.kind, "ipset")
            self.assertEqual(list_editor.display_path, "lists/ipset-youtube.txt")
            self.assertEqual(list_editor.base_display_path, "lists/base/ipset-youtube.txt")
            self.assertEqual(list_editor.user_display_path, "lists/user/ipset-youtube.txt")
            self.assertEqual(list_editor.base_text, "1.1.1.1\n")
            self.assertEqual(list_editor.user_text, "2.2.2.2\n")
            self.assertEqual(list_editor.text, "1.1.1.1\n2.2.2.2\n")
            self.assertEqual(list_editor.base_entries_count, 1)
            self.assertEqual(list_editor.user_entries_count, 1)

            saved = service.save_profile_list_file_text("profile:0", "8.8.8.8\n")
            saved_text = (lists_dir / "user" / "ipset-youtube.txt").read_text(encoding="utf-8")
            final_text = (lists_dir / "ipset-youtube.txt").read_text(encoding="utf-8")

            self.assertIsNotNone(saved)
            self.assertEqual(saved_text, "8.8.8.8\n")
            self.assertEqual(final_text, "1.1.1.1\n8.8.8.8\n")

    def test_service_read_does_not_create_user_layer_for_base_only_list(self) -> None:
        # Чтение состояния редактора — read-only операция: user-слой и итоговый
        # файл материализуются только при сохранении, а не при открытии страницы.
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")
            store = _PresetStore(
                "--filter-tcp=80,443\n--hostlist=lists/youtube.txt\n--lua-desync=pass\n"
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            list_editor = service.get_profile_list_file_editor_state("profile:0")

            self.assertIsNotNone(list_editor)
            self.assertEqual(list_editor.display_path, "lists/youtube.txt")
            self.assertEqual(list_editor.base_text, "youtube.com\n")
            self.assertEqual(list_editor.user_text, "")
            self.assertEqual(list_editor.text, "youtube.com\n")
            self.assertEqual(list_editor.base_entries_count, 1)
            self.assertEqual(list_editor.user_entries_count, 0)
            self.assertFalse((lists_dir / "user" / "youtube.txt").exists())
            self.assertFalse((lists_dir / "youtube.txt").exists())

    def test_rebuild_all_lists_combines_service_files_like_other_lists(self) -> None:
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "user").mkdir()
            for name in ("other.txt", "ipset-all.txt", "ipset-ru.txt", "ipset-dns.txt", "ipset-exclude.txt", "netrogat.txt", "youtube.txt"):
                (lists_dir / "base" / name).write_text(f"base-{name}\n", encoding="utf-8")
                (lists_dir / "user" / name).write_text(f"user-{name}\n", encoding="utf-8")

            rebuilt = rebuild_all_layered_list_files(lists_dir)

            self.assertEqual(rebuilt, 7)
            for name in ("other.txt", "ipset-all.txt", "ipset-ru.txt", "ipset-dns.txt", "ipset-exclude.txt", "netrogat.txt", "youtube.txt"):
                self.assertEqual(
                    (lists_dir / name).read_text(encoding="utf-8"),
                    f"base-{name}\nuser-{name}\n",
                )

    def test_rebuild_all_skips_unreferenced_user_only_lists(self) -> None:
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "user").mkdir()
            (lists_dir / "base" / "i-ytimg.txt").write_text("i.ytimg.com\n", encoding="utf-8")
            (lists_dir / "user" / "i.ytimg.txt").write_text("qwen.ai\n", encoding="utf-8")

            rebuilt = rebuild_all_layered_list_files(lists_dir)

            self.assertEqual(rebuilt, 1)
            self.assertEqual((lists_dir / "i-ytimg.txt").read_text(encoding="utf-8"), "i.ytimg.com\n")
            self.assertFalse((lists_dir / "i.ytimg.txt").exists())

    def test_rebuild_all_accepts_referenced_user_only_safe_placeholder_lists(self) -> None:
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "user").mkdir()
            (lists_dir / "base" / "i-ytimg.txt").write_text("i.ytimg.com\n", encoding="utf-8")
            (lists_dir / "user" / "i.ytimg.txt").write_text("www.example.com\n", encoding="utf-8")

            rebuilt = rebuild_all_layered_list_files(lists_dir, user_only_file_names={"i.ytimg.txt"})

            self.assertEqual(rebuilt, 2)
            self.assertEqual((lists_dir / "i-ytimg.txt").read_text(encoding="utf-8"), "i.ytimg.com\n")
            self.assertEqual((lists_dir / "i.ytimg.txt").read_text(encoding="utf-8"), "www.example.com\n")

    def test_rebuild_all_rebuilds_referenced_user_only_real_lists(self) -> None:
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "user").mkdir(parents=True)
            (lists_dir / "user" / "custom.txt").write_text("qwen.ai\n", encoding="utf-8")

            rebuilt = rebuild_all_layered_list_files(lists_dir, user_only_file_names={"custom.txt"})

            self.assertEqual(rebuilt, 1)
            self.assertEqual((lists_dir / "custom.txt").read_text(encoding="utf-8"), "qwen.ai\n")

    def test_parallel_rebuilds_do_not_write_layered_files_at_same_time(self) -> None:
        from unittest.mock import patch

        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "user").mkdir()
            (lists_dir / "base" / "cloudflare.txt").write_text("cloudflare.com\n", encoding="utf-8")
            (lists_dir / "base" / "roblox.txt").write_text("roblox.com\n", encoding="utf-8")

            counter_lock = threading.Lock()
            active_writes = 0
            max_active_writes = 0
            errors: list[BaseException] = []

            def slow_write(path: str, content: str) -> None:
                nonlocal active_writes, max_active_writes
                with counter_lock:
                    active_writes += 1
                    max_active_writes = max(max_active_writes, active_writes)
                try:
                    time.sleep(0.05)
                    Path(path).write_text(content, encoding="utf-8")
                finally:
                    with counter_lock:
                        active_writes -= 1

            def rebuild(name: str) -> None:
                try:
                    rebuild_profile_list_file(lists_dir, name)
                except BaseException as exc:
                    errors.append(exc)

            with patch("lists.core.layered_files.write_text_file", side_effect=slow_write):
                first = threading.Thread(target=rebuild, args=("cloudflare.txt",))
                second = threading.Thread(target=rebuild, args=("roblox.txt",))
                first.start()
                second.start()
                first.join()
                second.join()

            self.assertEqual(errors, [])
            self.assertEqual(max_active_writes, 1)

    def test_rebuild_user_only_safe_placeholder_raises_when_final_is_empty(self) -> None:
        from unittest.mock import patch

        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "user").mkdir(parents=True)
            (lists_dir / "user" / "i.ytimg.txt").write_text("www.example.com\n", encoding="utf-8")

            def write_empty(path: str, _content: str) -> None:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_text("", encoding="utf-8")

            with patch("lists.core.layered_files.write_text_file", side_effect=write_empty):
                with self.assertRaisesRegex(ValueError, "0 КБ"):
                    rebuild_profile_list_file(lists_dir, "i.ytimg.txt")

    def test_rebuild_accepts_non_empty_final_without_full_content_check(self) -> None:
        from unittest.mock import patch

        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "user").mkdir(parents=True)
            (lists_dir / "user" / "custom.txt").write_text("qwen.ai\n", encoding="utf-8")

            def write_partial(path: str, _content: str) -> None:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_text("partial\n", encoding="utf-8")

            with patch("lists.core.layered_files.write_text_file", side_effect=write_partial):
                rebuild_profile_list_file(lists_dir, "custom.txt")

    def test_rebuild_empty_hostlist_seeds_safe_placeholder(self) -> None:
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "user").mkdir()
            (lists_dir / "base" / "empty.txt").write_text("", encoding="utf-8")
            (lists_dir / "user" / "empty.txt").write_text("", encoding="utf-8")

            rebuild_profile_list_file(lists_dir, "empty.txt")

            self.assertEqual((lists_dir / "user" / "empty.txt").read_text(encoding="utf-8"), "www.example.com\n")
            self.assertEqual((lists_dir / "empty.txt").read_text(encoding="utf-8"), "www.example.com\n")

    def test_rebuild_empty_ipset_seeds_safe_placeholder_ip(self) -> None:
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "user").mkdir()
            (lists_dir / "base" / "ipset-empty.txt").write_text("", encoding="utf-8")
            (lists_dir / "user" / "ipset-empty.txt").write_text("", encoding="utf-8")

            rebuild_profile_list_file(lists_dir, "ipset-empty.txt")

            self.assertEqual((lists_dir / "user" / "ipset-empty.txt").read_text(encoding="utf-8"), "123.123.123.123\n")
            self.assertEqual((lists_dir / "ipset-empty.txt").read_text(encoding="utf-8"), "123.123.123.123\n")

    def test_rebuild_raises_when_final_file_is_zero_bytes(self) -> None:
        from unittest.mock import patch

        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "user").mkdir()
            (lists_dir / "base" / "netrogat.txt").write_text("base.example\n", encoding="utf-8")
            (lists_dir / "user" / "netrogat.txt").write_text("qwen.ai\n", encoding="utf-8")

            def write_empty(path: str, _content: str) -> None:
                Path(path).parent.mkdir(parents=True, exist_ok=True)
                Path(path).write_text("", encoding="utf-8")

            with patch("lists.core.layered_files.write_text_file", side_effect=write_empty):
                with self.assertRaisesRegex(ValueError, "0 КБ"):
                    rebuild_profile_list_file(lists_dir, "netrogat.txt")

    def test_service_exclusion_ipset_ru_file_is_gui_editable(self) -> None:
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "user").mkdir()
            (lists_dir / "base" / "ipset-ru.txt").write_text("1.1.1.1\n", encoding="utf-8")
            (lists_dir / "user" / "ipset-ru.txt").write_text("2.2.2.2\n", encoding="utf-8")
            store = _PresetStore(
                "--name=Исключения\n"
                "--filter-tcp=80,443-65535\n"
                "--ipset-exclude=lists/ipset-ru.txt\n"
                "--ipset-exclude=lists/ipset-dns.txt\n"
                "--ipset-exclude=lists/ipset-exclude.txt\n"
                "--lua-desync=pass\n"
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            list_editor = service.get_profile_list_file_editor_state("profile:0")

            self.assertIsNotNone(list_editor)
            self.assertTrue(list_editor.editable)
            self.assertEqual(list_editor.kind, "ipset")
            self.assertEqual(list_editor.display_path, "lists/ipset-ru.txt")
            self.assertEqual(list_editor.base_text, "1.1.1.1\n")
            self.assertEqual(list_editor.user_text, "2.2.2.2\n")
            self.assertEqual(list_editor.text, "1.1.1.1\n2.2.2.2\n")

    def test_service_exclusion_dns_file_is_not_gui_editable(self) -> None:
        preset = parse_preset_text(
            "--name=Исключения\n"
            "--filter-tcp=80,443-65535\n"
            "--ipset-exclude=lists/ipset-dns.txt\n"
            "--lua-desync=pass\n",
            engine=ENGINE_WINWS2,
        )

        reference = profile_list_file_reference(preset.profiles[0], Path("/tmp/lists"))

        self.assertFalse(reference.editable)
        self.assertEqual(reference.kind, "ipset")
        self.assertEqual(reference.file_name, "ipset-dns.txt")
        self.assertEqual(reference.display_path, "lists/ipset-dns.txt")
        self.assertIn("служебный список", reference.error_text)

    def test_editor_state_for_primary_kind_switch_preview_remaps_file(self) -> None:
        # Превью переключения типа на primary-фильтре: сервис ремапит
        # youtube.txt → ipset-youtube.txt, и состояние редактора описывает
        # ДРУГОЙ файл, чем пара запроса. Идентичность результата на странице —
        # эхо пары запроса; сравнение имён файлов здесь не сходится по
        # построению (AC9, регрессия «бесконечная загрузка файла списка»).
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            (lists_dir / "base").mkdir(parents=True)
            (lists_dir / "base" / "youtube.txt").write_text("youtube.com\n", encoding="utf-8")
            (lists_dir / "base" / "ipset-youtube.txt").write_text("1.1.1.1\n", encoding="utf-8")
            store = _PresetStore(
                "--filter-tcp=80,443\n"
                "--hostlist=lists/youtube.txt\n"
                "--lua-desync=pass\n"
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            state = service.get_profile_list_file_editor_state(
                "profile:0",
                filter_kind="ipset",
                filter_value="lists/youtube.txt",
            )

            self.assertIsNotNone(state)
            self.assertTrue(state.editable)
            self.assertEqual(state.kind, "ipset")
            self.assertEqual(state.display_path, "lists/ipset-youtube.txt")

    def test_editor_state_for_exclude_kind_switch_keeps_current_file(self) -> None:
        # AC10: у exclude-фильтров парного типа нет — превью с чужим типом
        # не ремапит netrogat в служебные ipset-файлы, состояние остаётся
        # родным hostlist-файлом профиля.
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            lists_dir.mkdir(parents=True)
            for name in ("ipset-ru.txt", "ipset-dns.txt", "ipset-exclude.txt"):
                (lists_dir / name).write_text("1.1.1.1\n", encoding="utf-8")
            store = _PresetStore(
                "--name=Все сайты (хостлисты)\n"
                "--filter-tcp=80,443-65535\n"
                "--hostlist-exclude=lists/netrogat.txt\n"
                "--lua-desync=pass\n"
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            state = service.get_profile_list_file_editor_state(
                "profile:0",
                filter_kind="ipset",
                filter_value="lists/netrogat.txt",
            )

            self.assertIsNotNone(state)
            self.assertTrue(state.editable)
            self.assertEqual(state.kind, "hostlist")
            self.assertEqual(state.display_path, "lists/netrogat.txt")

    def test_read_editor_state_keeps_final_list_intact_when_base_is_missing(self) -> None:
        # Регрессия: открытие профиля «Все сайты (айпи)» при отсутствующей
        # lists/base/ipset-ru.txt создавало user-слой с плейсхолдером и
        # ПЕРЕЗАПИСЫВАЛО рабочий lists/ipset-ru.txt строкой 123.123.123.123.
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            lists_dir = root / "lists"
            lists_dir.mkdir(parents=True)
            (lists_dir / "ipset-ru.txt").write_text("1.2.3.0/24\n5.6.7.0/24\n", encoding="utf-8")
            store = _PresetStore(
                "--name=Все сайты (айпи)\n"
                "--filter-tcp=80,443-65535\n"
                "--ipset-exclude=lists/ipset-ru.txt\n"
                "--ipset-exclude=lists/ipset-dns.txt\n"
                "--ipset-exclude=lists/ipset-exclude.txt\n"
                "--lua-desync=pass\n"
            )
            feature = SimpleNamespace(
                _presets_feature=store,
                _app_paths=AppPaths(user_root=root, local_root=root),
            )
            service = ProfilePresetService(feature, "zapret2_mode")

            list_editor = service.get_profile_list_file_editor_state("profile:0")

            self.assertIsNotNone(list_editor)
            self.assertTrue(list_editor.editable)
            self.assertEqual(list_editor.display_path, "lists/ipset-ru.txt")
            self.assertEqual(
                (lists_dir / "ipset-ru.txt").read_text(encoding="utf-8"),
                "1.2.3.0/24\n5.6.7.0/24\n",
            )
            self.assertFalse((lists_dir / "user" / "ipset-ru.txt").exists())

    def test_passive_rebuild_keeps_foreign_final_when_layers_are_empty(self) -> None:
        # Пассивная пересборка (старт, ensure, rebuild_all) не должна затирать
        # плейсхолдером или удалять итоговый файл, которым управляет не
        # слоёная система (скачанный ipset-ru.txt при отсутствующей базе).
        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            lists_dir.mkdir(parents=True)
            (lists_dir / "ipset-ru.txt").write_text("1.2.3.0/24\n5.6.7.0/24\n", encoding="utf-8")

            # Оба слоя отсутствуют: раньше итоговый файл удалялся.
            rebuild_profile_list_file(lists_dir, "ipset-ru.txt")
            self.assertEqual(
                (lists_dir / "ipset-ru.txt").read_text(encoding="utf-8"),
                "1.2.3.0/24\n5.6.7.0/24\n",
            )

            # Пустой user-слой существует: раньше сеялся плейсхолдер поверх финала.
            (lists_dir / "user").mkdir()
            (lists_dir / "user" / "ipset-ru.txt").write_text("", encoding="utf-8")
            rebuild_profile_list_file(lists_dir, "ipset-ru.txt")
            self.assertEqual(
                (lists_dir / "ipset-ru.txt").read_text(encoding="utf-8"),
                "1.2.3.0/24\n5.6.7.0/24\n",
            )
            self.assertEqual(
                (lists_dir / "user" / "ipset-ru.txt").read_text(encoding="utf-8"),
                "",
            )

    def test_explicit_clear_still_rebuilds_final_with_placeholder(self) -> None:
        # Явная правка user-слоя сохраняет прежнюю семантику: очистка записей
        # user-only списка обязана пересобрать финал (в плейсхолдер), а не
        # оставить в lists/<file> удалённые записи.
        from lists.core.layered_files import write_profile_user_list_text

        with TemporaryDirectory() as temp_dir:
            lists_dir = Path(temp_dir) / "lists"
            (lists_dir / "user").mkdir(parents=True)
            (lists_dir / "user" / "custom.txt").write_text("qwen.ai\n", encoding="utf-8")
            rebuild_profile_list_file(lists_dir, "custom.txt")
            self.assertEqual(
                (lists_dir / "custom.txt").read_text(encoding="utf-8"),
                "qwen.ai\n",
            )

            write_profile_user_list_text(lists_dir, "custom.txt", "")

            self.assertEqual(
                (lists_dir / "custom.txt").read_text(encoding="utf-8"),
                "www.example.com\n",
            )

    def test_service_exclusion_netrogat_file_is_gui_editable(self) -> None:
        preset = parse_preset_text(
            "--name=Исключения\n"
            "--filter-tcp=80,443-65535\n"
            "--hostlist-exclude=lists/netrogat.txt\n"
            "--lua-desync=pass\n",
            engine=ENGINE_WINWS2,
        )

        reference = profile_list_file_reference(preset.profiles[0], Path("/tmp/lists"))

        self.assertTrue(reference.editable)
        self.assertEqual(reference.kind, "hostlist")
        self.assertEqual(reference.file_name, "netrogat.txt")
        self.assertEqual(reference.display_path, "lists/netrogat.txt")
        self.assertEqual(reference.user_display_path, "lists/user/netrogat.txt")


if __name__ == "__main__":
    unittest.main()
