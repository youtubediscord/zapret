"""Инвариант поставки списков.

Каждый lists/<file>.txt, на который ссылаются all_profiles.txt и builtin
preset-ы, обязан присутствовать в build source (private_zapretgui/dist/lists)
либо генерироваться приложением из встроенных баз. Иначе после установки
пресет падает с «Preset содержит ссылки на отсутствующие файлы»
(история: netrogat.txt удалялся сборкой как generated, но не регенерировался).
"""

from __future__ import annotations

import re
import unittest
from pathlib import Path

PUBLIC_ROOT = Path(__file__).resolve().parents[1]
PRIVATE_ROOT = PUBLIC_ROOT.parent / "private_zapretgui"
ALL_PROFILES_PATH = PRIVATE_ROOT / "resources" / "profile" / "templates" / "all_profiles.txt"
BUILTIN_PRESETS_ROOT = PUBLIC_ROOT / "src" / "presets" / "builtin"
SHIPPED_LISTS_DIR = PRIVATE_ROOT / "dist" / "lists"

# Эти итоговые файлы приложение собирает само из встроенных баз
# (lists/core/embedded_defaults.py), в поставке их быть не должно.
RUNTIME_GENERATED_LIST_NAMES = frozenset({"other.txt", "ipset-all.txt", "ipset-ru.txt"})

_LIST_REFERENCE_RE = re.compile(r"lists[/\\]([A-Za-z0-9_.\- ]+?\.txt)", flags=re.IGNORECASE)


def _referenced_list_names(text: str) -> set[str]:
    names: set[str] = set()
    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        for match in _LIST_REFERENCE_RE.finditer(line):
            names.add(match.group(1).strip().lower())
    return names


def _collect_required_list_names() -> dict[str, set[str]]:
    """Возвращает имя списка -> множество источников, которые на него ссылаются."""
    required: dict[str, set[str]] = {}

    sources: list[tuple[str, Path]] = [("all_profiles.txt", ALL_PROFILES_PATH)]
    sources.extend(
        (str(path.relative_to(BUILTIN_PRESETS_ROOT)), path)
        for path in sorted(BUILTIN_PRESETS_ROOT.rglob("*.txt"))
    )

    for source_name, path in sources:
        text = path.read_text(encoding="utf-8", errors="replace")
        for list_name in _referenced_list_names(text):
            required.setdefault(list_name, set()).add(source_name)
    return required


class ShippedListsInvariantTest(unittest.TestCase):
    def setUp(self) -> None:
        if not ALL_PROFILES_PATH.is_file():
            self.skipTest(f"Нет private-репозитория: {ALL_PROFILES_PATH}")
        if not SHIPPED_LISTS_DIR.is_dir():
            self.skipTest(f"Нет build source списков: {SHIPPED_LISTS_DIR}")

    def test_every_referenced_list_file_is_shipped_or_runtime_generated(self) -> None:
        shipped = {path.name.lower() for path in SHIPPED_LISTS_DIR.glob("*.txt")}
        available = shipped | {name.lower() for name in RUNTIME_GENERATED_LIST_NAMES}

        missing = {
            list_name: sorted(sources)
            for list_name, sources in sorted(_collect_required_list_names().items())
            if list_name not in available
        }

        self.assertEqual(
            missing,
            {},
            "Списки, на которые ссылаются профили/пресеты, отсутствуют в поставке "
            f"({SHIPPED_LISTS_DIR}): {missing}",
        )

    def test_runtime_generated_lists_are_not_shipped_as_plain_files(self) -> None:
        """Generated-файлы не должны попадать в build source: сборка их чистит,
        а приложение собирает заново из embedded-баз."""
        shipped = {path.name.lower() for path in SHIPPED_LISTS_DIR.glob("*.txt")}
        overlap = sorted(shipped & {name.lower() for name in RUNTIME_GENERATED_LIST_NAMES})
        self.assertEqual(overlap, [])


if __name__ == "__main__":
    unittest.main()
