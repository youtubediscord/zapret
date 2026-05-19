from __future__ import annotations

from pathlib import Path
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]


class ProfileStatusWordingTests(unittest.TestCase):
    def test_profile_code_does_not_use_old_disabled_wording(self) -> None:
        forbidden = ("Отклю" + "чено", "от" + "ключ")
        files = [
            path
            for root in (PROJECT_ROOT / "src" / "profile",)
            for path in root.rglob("*")
            if path.is_file() and path.suffix in {".py", ".txt"}
        ]

        matches: list[str] = []
        for path in files:
            text = path.read_text(encoding="utf-8", errors="replace")
            for word in forbidden:
                if word in text:
                    matches.append(str(path.relative_to(PROJECT_ROOT)))

        self.assertEqual(matches, [])


if __name__ == "__main__":
    unittest.main()
