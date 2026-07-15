from __future__ import annotations

import os
import sys
import unittest
from pathlib import Path

PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PyQt6.QtWidgets import QApplication

import profile.ui.profile_icon as profile_icon
from profile.ui.simple_icons_bundle import SIMPLE_ICON_SVGS


def _catalog_simple_slugs() -> set[str]:
    """Собирает simple-слаги из каталога иконок тем же способом, что и генератор."""
    import profile.icons as profile_icons

    slugs: set[str] = set()
    for attr_name in dir(profile_icons):
        attr = getattr(profile_icons, attr_name)
        if not isinstance(attr, dict):
            continue
        for value in attr.values():
            icon_name = str(getattr(value, "icon_name", "") or "")
            if not icon_name.startswith("simple:"):
                continue
            slug = icon_name.removeprefix("simple:").partition(":")[0]
            slug = slug.strip().lower().replace("-", "")
            if slug:
                slugs.add(slug)
    return slugs


class SimpleIconsBundleTests(unittest.TestCase):
    """Рантайм рисует брендовые иконки из сгенерированного бандла, без simplepycons."""

    @classmethod
    def setUpClass(cls) -> None:
        cls._app = QApplication.instance() or QApplication([])

    def setUp(self) -> None:
        profile_icon._PROFILE_PIXMAP_CACHE.clear()

    def test_bundle_covers_all_catalog_slugs(self) -> None:
        """При добавлении сервиса в profile/icons.py нужно перегенерировать бандл:
        PYTHONPATH=src python tools/generate_profile_icon_bundle.py"""
        catalog_slugs = _catalog_simple_slugs()
        self.assertTrue(catalog_slugs, "каталог не дал ни одного simple-слага")
        missing = sorted(catalog_slugs - set(SIMPLE_ICON_SVGS))
        self.assertEqual(missing, [], f"бандл не покрывает слаги каталога: {missing}")

    def test_bundle_entries_are_valid_svgs(self) -> None:
        for slug, (primary_color, raw_svg) in SIMPLE_ICON_SVGS.items():
            with self.subTest(slug=slug):
                self.assertTrue(raw_svg.lstrip().startswith("<svg"), "не SVG")
                if primary_color:
                    self.assertRegex(primary_color, r"^#[0-9A-Fa-f]{6}$")

    def test_simple_icon_renders_from_bundle(self) -> None:
        pixmap = profile_icon.profile_icon_pixmap(
            "simple:youtube:YT",
            color="#FF0000",
            size=18,
        )

        self.assertFalse(pixmap.isNull())
        cache_kinds = {key[0] for key in profile_icon._PROFILE_PIXMAP_CACHE}
        self.assertIn("simple", cache_kinds, "иконка не отрисована из бандла")
        self.assertNotIn("initials", cache_kinds, "не должно быть заглушки для иконки из бандла")

    def test_vencord_icon_renders_from_bundle(self) -> None:
        pixmap = profile_icon.profile_icon_pixmap(
            "simple:vencord:VC",
            color="#EB7396",
            size=18,
        )

        self.assertFalse(pixmap.isNull())
        self.assertTrue(any(key[0] == "simple" and key[1] == "vencord" for key in profile_icon._PROFILE_PIXMAP_CACHE))

    def test_unknown_slug_falls_back_to_initials(self) -> None:
        pixmap = profile_icon.profile_icon_pixmap(
            "simple:definitely-not-in-bundle:NB",
            color="#3B82F6",
            size=18,
        )

        self.assertFalse(pixmap.isNull())
        cache_kinds = {key[0] for key in profile_icon._PROFILE_PIXMAP_CACHE}
        self.assertIn("initials", cache_kinds)

    def test_runtime_never_imports_simplepycons(self) -> None:
        """Регрессия: импорт simplepycons (~3400 модулей, ~2.6с) морозил первую
        отрисовку списка профилей. Рантайм обязан обходиться бандлом."""
        for slug in list(SIMPLE_ICON_SVGS)[:5]:
            profile_icon.profile_icon_pixmap(f"simple:{slug}:XX", color="", size=18)

        self.assertNotIn("simplepycons", sys.modules)

    def test_profile_icon_module_has_no_simplepycons_reference(self) -> None:
        source = (PROJECT_SRC / "profile" / "ui" / "profile_icon.py").read_text(encoding="utf-8")
        self.assertNotIn("import simplepycons", source)
        self.assertNotIn("from simplepycons", source)


if __name__ == "__main__":
    unittest.main()
