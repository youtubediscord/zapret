from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path


PROJECT_SRC = Path(__file__).resolve().parents[1] / "src"
if str(PROJECT_SRC) not in sys.path:
    sys.path.insert(0, str(PROJECT_SRC))


class IgnoredTargetsBehaviorTests(unittest.TestCase):
    def test_exact_domains_are_web_telegram_only(self) -> None:
        from orchestra.ignored_targets import get_orchestra_ignored_exact_domains

        domains = get_orchestra_ignored_exact_domains()
        self.assertTrue(domains)
        for domain in domains:
            self.assertIn(".web.telegram.org", domain)

    def test_ignored_target_matches_exact_relay_domain(self) -> None:
        from orchestra.ignored_targets import is_orchestra_ignored_target

        self.assertTrue(is_orchestra_ignored_target("zws4.web.telegram.org"))
        self.assertTrue(is_orchestra_ignored_target("ZWS4.WEB.TELEGRAM.ORG."))

    def test_non_relay_domains_are_not_ignored(self) -> None:
        from orchestra.ignored_targets import is_orchestra_ignored_target

        self.assertFalse(is_orchestra_ignored_target("t.me"))
        self.assertFalse(is_orchestra_ignored_target("telegram.org"))
        self.assertFalse(is_orchestra_ignored_target(""))


class IgnoredTargetsLazyImportTests(unittest.TestCase):
    def test_orchestra_facade_import_does_not_pull_telegram_proxy(self) -> None:
        """Импорт фасада orchestra не должен исполнять пакет telegram_proxy.

        Импорт telegram_proxy тянет wss_proxy/mtproxy/asyncio и стоил ~240 мс
        на старте GUI (метрика StartupFeatureFacadeImport.orchestra).
        """
        code = (
            "import sys\n"
            "import app.feature_facades.orchestra\n"
            "import orchestra.ignored_targets\n"
            "loaded = [m for m in sys.modules if m.startswith('telegram_proxy')]\n"
            "assert not loaded, f'telegram_proxy imported at startup: {loaded}'\n"
        )
        result = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            env={"PYTHONPATH": str(PROJECT_SRC), "SYSTEMROOT": __import__("os").environ.get("SYSTEMROOT", "")},
            cwd=str(PROJECT_SRC.parent),
        )
        self.assertEqual(result.returncode, 0, msg=f"stdout={result.stdout}\nstderr={result.stderr}")


if __name__ == "__main__":
    unittest.main()
