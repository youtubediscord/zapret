from __future__ import annotations

import ast
from pathlib import Path
import unittest


SRC_ROOT = Path(__file__).resolve().parents[1] / "src"

FRESHNESS_GUARD_MARKERS = (
    "_is_current_worker_finish",
    "_accept_current",
    "_is_current_request_finish",
    ".is_current(",
    "accept_worker_finish",
    "current_worker",
    "_runtime_worker",
)


class WorkerFinishedPendingGuardContractTests(unittest.TestCase):
    def test_pending_worker_finished_handlers_check_current_worker_or_request(self) -> None:
        offenders: list[str] = []
        for path in SRC_ROOT.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            if "_pending" not in text or "worker_finished" not in text:
                continue

            tree = ast.parse(text)
            for node in ast.walk(tree):
                if not isinstance(node, ast.FunctionDef):
                    continue
                if not node.name.startswith("_on_") or not node.name.endswith("worker_finished"):
                    continue

                source = ast.get_source_segment(text, node) or ""
                if "_pending" not in source:
                    continue
                if any(marker in source for marker in FRESHNESS_GUARD_MARKERS):
                    continue

                rel_path = path.relative_to(SRC_ROOT).as_posix()
                offenders.append(f"{rel_path}:{node.lineno}:{node.name}")

        self.assertEqual([], offenders)


if __name__ == "__main__":
    unittest.main()
