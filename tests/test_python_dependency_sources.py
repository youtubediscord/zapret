from __future__ import annotations

import re
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ROLE_FILES = (
    "requirements-runtime.txt",
    "requirements-build.txt",
    "requirements-publish.txt",
    "requirements-dev.txt",
)


def _package_lines(path: Path) -> list[str]:
    return [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith(("#", "-r "))
    ]


class PythonDependencySourcesTests(unittest.TestCase):
    def test_full_environment_includes_each_dependency_role_once(self) -> None:
        full_requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")

        for filename in ("requirements-build.txt", "requirements-publish.txt", "requirements-dev.txt"):
            self.assertEqual(full_requirements.count(f"-r {filename}"), 1)

    def test_direct_dependency_versions_are_exact_and_not_duplicated(self) -> None:
        seen: dict[str, str] = {}

        for filename in ROLE_FILES:
            for requirement in _package_lines(ROOT / filename):
                self.assertRegex(
                    requirement,
                    r"^[A-Za-z0-9_.-]+==[A-Za-z0-9_.!+-]+$",
                    msg=f"{filename}: версия должна быть закреплена точно: {requirement}",
                )
                package = re.split(r"==", requirement, maxsplit=1)[0].replace("_", "-").casefold()
                self.assertNotIn(
                    package,
                    seen,
                    msg=f"{package} одновременно задан в {seen.get(package)} и {filename}",
                )
                seen[package] = filename

    def test_active_windows_workflow_uses_canonical_build_requirements(self) -> None:
        workflow = (ROOT / ".github" / "workflows" / "windows-release.yml").read_text(
            encoding="utf-8"
        )

        self.assertIn("-r requirements-build.txt", workflow)
        for package in ("PyQt6", "Nuitka", "PyInstaller", "TgCrypto"):
            self.assertNotRegex(workflow, rf"pip install[^\n]*\b{package}\b")


if __name__ == "__main__":
    unittest.main()
