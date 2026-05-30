from __future__ import annotations

import ast
import importlib
import inspect
import unittest


class FeatureAssemblyImportsTests(unittest.TestCase):
    def test_build_app_features_imports_existing_feature_symbols(self) -> None:
        from app.feature_assembly import build_app_features

        tree = ast.parse(inspect.getsource(build_app_features))
        missing: list[str] = []
        for node in ast.walk(tree):
            if not isinstance(node, ast.ImportFrom):
                continue
            if not node.module or not node.module.startswith("app.feature_facades."):
                continue

            module = importlib.import_module(node.module)
            for alias in node.names:
                if alias.name == "*":
                    continue
                if not hasattr(module, alias.name):
                    missing.append(f"{node.module}.{alias.name}")

        self.assertEqual(missing, [])


if __name__ == "__main__":
    unittest.main()
