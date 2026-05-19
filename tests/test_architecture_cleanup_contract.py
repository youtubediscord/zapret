from __future__ import annotations

import ast
import inspect
from pathlib import Path
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"


class ArchitectureCleanupContractTests(unittest.TestCase):
    def _module_tree(self, relative_path: str) -> ast.Module:
        return ast.parse((SRC_ROOT / relative_path).read_text(encoding="utf-8"))

    def test_page_deps_builders_do_not_receive_broad_context(self) -> None:
        for relative_path in ("ui/page_deps/system.py", "ui/page_deps/presets.py"):
            with self.subTest(path=relative_path):
                tree = self._module_tree(relative_path)
                builder_args: list[str] = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith("build_"):
                        builder_args.extend(arg.arg for arg in node.args.args)
                        builder_args.extend(arg.arg for arg in node.args.kwonlyargs)

                self.assertNotIn(
                    "context",
                    builder_args,
                    "page deps builder-ы не должны получать общий PageDepsContext",
                )

    def test_page_deps_common_does_not_define_broad_page_deps_context(self) -> None:
        tree = self._module_tree("ui/page_deps/common.py")
        class_names = {
            node.name
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef)
        }

        self.assertNotIn(
            "PageDepsContext",
            class_names,
            "общий PageDepsContext нельзя оставлять как точку возврата к широким deps",
        )

    def test_page_deps_specs_cover_required_builder_parameters(self) -> None:
        from ui.page_composition import PAGE_DEPS_BUILDERS

        for page_name, spec in PAGE_DEPS_BUILDERS.items():
            with self.subTest(page=page_name.name):
                provided = {"page_name"}
                provided.update(f"{feature_name}_feature" for feature_name in spec.features)
                provided.update(spec.actions)
                if spec.include_ui_state_store:
                    provided.add("ui_state_store")

                signature = inspect.signature(spec.builder)
                required = {
                    name
                    for name, parameter in signature.parameters.items()
                    if parameter.default is inspect.Parameter.empty
                    and parameter.kind
                    in (
                        inspect.Parameter.POSITIONAL_OR_KEYWORD,
                        inspect.Parameter.KEYWORD_ONLY,
                    )
                }

                self.assertTrue(
                    required <= provided,
                    f"{page_name.name}: PageDepsSpec не передаёт {sorted(required - provided)}",
                )

    def test_preset_switch_worker_requires_fast_switch_contract(self) -> None:
        source = (SRC_ROOT / "winws_runtime" / "runtime" / "control_workers.py").read_text(encoding="utf-8")
        tree = ast.parse(source)
        worker = next(
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.ClassDef) and node.name == "PresetSwitchWorker"
        )

        for node in ast.walk(worker):
            if isinstance(node, ast.Call):
                if isinstance(node.func, ast.Name) and node.func.id == "getattr":
                    args = node.args
                    if len(args) >= 2 and isinstance(args[1], ast.Constant):
                        self.assertNotEqual(args[1].value, "switch_preset_file_fast")
                if isinstance(node.func, ast.Attribute):
                    self.assertNotEqual(
                        node.func.attr,
                        "start_from_preset_file",
                        "PresetSwitchWorker не должен иметь fallback на полный запуск preset",
                    )


if __name__ == "__main__":
    unittest.main()
