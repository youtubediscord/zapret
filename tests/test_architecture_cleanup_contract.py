from __future__ import annotations

import ast
import inspect
from pathlib import Path
from types import SimpleNamespace
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

    def test_window_page_deps_sources_include_all_page_actions(self) -> None:
        from main.window_page_deps_setup import build_window_page_deps_sources
        from main.window_page_actions import WindowPageActions
        from ui.page_composition import PAGE_DEPS_BUILDERS

        required_actions = {
            action_name
            for spec in PAGE_DEPS_BUILDERS.values()
            for action_name in spec.actions
        }
        required_features = {
            feature_name
            for spec in PAGE_DEPS_BUILDERS.values()
            for feature_name in spec.features
        }
        features = SimpleNamespace(**{name: object() for name in required_features})
        state = SimpleNamespace(ui=object())
        page_actions = SimpleNamespace(**{name: object() for name in WindowPageActions.__dataclass_fields__})

        sources = build_window_page_deps_sources(
            features=features,
            state=state,
            page_actions=page_actions,
        )

        self.assertTrue(
            required_actions <= set(sources.actions),
            f"PageDepsSources.actions не содержит {sorted(required_actions - set(sources.actions))}",
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

    def test_fast_switch_contract_does_not_call_full_start_pipeline_inside_runner(self) -> None:
        for relative_path, class_name in (
            ("winws_runtime/runners/zapret1_runner.py", "Winws1StrategyRunner"),
            ("winws_runtime/runners/zapret2_runner.py", "Winws2StrategyRunner"),
        ):
            with self.subTest(path=relative_path):
                tree = self._module_tree(relative_path)
                runner = next(
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, ast.ClassDef) and node.name == class_name
                )
                switch_method = next(
                    node
                    for node in runner.body
                    if isinstance(node, ast.FunctionDef) and node.name == "switch_preset_file_fast"
                )

                for node in ast.walk(switch_method):
                    if isinstance(node, ast.Attribute):
                        self.assertNotEqual(
                            node.attr,
                            "_start_from_preset_file_locked",
                            "switch_preset_file_fast не должен откатываться в полный start pipeline",
                        )

    def test_source_does_not_reference_obsolete_list_sidecars(self) -> None:
        patterns = (".base.txt", ".user.txt")
        offenders: list[str] = []
        for path in SRC_ROOT.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for line_number, line in enumerate(text.splitlines(), 1):
                if any(pattern in line for pattern in patterns):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: {line.strip()}")

        self.assertEqual(
            offenders,
            [],
            "src не должен знать старые list-sidecar файлы *.base.txt / *.user.txt",
        )

    def test_settings_normalize_does_not_migrate_old_winws1_folder_schema(self) -> None:
        source = (SRC_ROOT / "settings" / "normalize.py").read_text(encoding="utf-8")
        forbidden = (
            "_prepare_winws1_preset_folders",
            '"all-tcp-udp"',
            '"game-filter"',
            '"circular"',
        )

        for pattern in forbidden:
            with self.subTest(pattern=pattern):
                self.assertNotIn(
                    pattern,
                    source,
                    "settings.normalize не должен знать старую схему папок winws1",
                )

    def test_sidebar_expanded_save_has_single_state_source(self) -> None:
        patterns = (
            "sidebar_expanded_save_pending",
            "sidebar_expanded_save_start_scheduled",
            "_sync_sidebar_expanded_save_compat_fields",
            "_theme_persist_pending",
            "_theme_persist_start_scheduled",
            "_appearance_save_pending",
            "_appearance_save_start_scheduled",
        )
        offenders: list[str] = []
        for path in SRC_ROOT.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for line_number, line in enumerate(text.splitlines(), 1):
                if any(pattern in line for pattern in patterns):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: {line.strip()}")

        self.assertEqual(
            offenders,
            [],
            "состояние отложенного сохранения должно жить только в LatestValueWorkerState",
        )

    def test_source_does_not_use_old_display_theme_names(self) -> None:
        patterns = ("Светлая синяя", "Темная синяя", "Светлая", "Темная")
        offenders: list[str] = []
        for path in SRC_ROOT.rglob("*.py"):
            text = path.read_text(encoding="utf-8", errors="replace")
            for line_number, line in enumerate(text.splitlines(), 1):
                if any(pattern in line for pattern in patterns):
                    offenders.append(f"{path.relative_to(REPO_ROOT)}:{line_number}: {line.strip()}")

        self.assertEqual(
            offenders,
            [],
            "внутренняя логика темы должна использовать только dark/light/system",
        )


if __name__ == "__main__":
    unittest.main()
