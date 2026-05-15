from __future__ import annotations

import re
import sys
import ast
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_ROOT = REPO_ROOT / "src"
THIS_FILE = Path(__file__).resolve()


@dataclass(frozen=True, slots=True)
class Problem:
    path: Path
    line: int
    message: str
    text: str = ""

    def format(self) -> str:
        rel = self.path.relative_to(REPO_ROOT)
        suffix = f": {self.text.strip()}" if self.text.strip() else ""
        return f"{rel}:{self.line}: {self.message}{suffix}"


def _python_files() -> list[Path]:
    return [
        path
        for path in SRC_ROOT.rglob("*.py")
        if path.resolve() != THIS_FILE
    ]


def _lines(path: Path) -> list[str]:
    return path.read_text(encoding="utf-8", errors="replace").splitlines()


def _page_name_dict_keys(path: Path, dict_name: str) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
    for node in tree.body:
        value = None
        target_name = None
        if isinstance(node, ast.Assign):
            value = node.value
            for target in node.targets:
                if isinstance(target, ast.Name):
                    target_name = target.id
                    break
        elif isinstance(node, ast.AnnAssign):
            value = node.value
            if isinstance(node.target, ast.Name):
                target_name = node.target.id

        if target_name != dict_name or not isinstance(value, ast.Dict):
            continue

        keys: set[str] = set()
        for key in value.keys:
            if (
                isinstance(key, ast.Attribute)
                and isinstance(key.value, ast.Name)
                and key.value.id == "PageName"
            ):
                keys.add(key.attr)
        return keys
    return set()


def _under(path: Path, *parts: str) -> bool:
    rel = path.relative_to(REPO_ROOT).as_posix()
    return any(rel.startswith(part) for part in parts)


def _scan_lines(
    files: list[Path],
    pattern: re.Pattern[str],
    message: str,
    *,
    allowed_paths: set[str] | None = None,
) -> list[Problem]:
    allowed_paths = allowed_paths or set()
    problems: list[Problem] = []
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in allowed_paths:
            continue
        for index, line in enumerate(_lines(path), start=1):
            if pattern.search(line):
                problems.append(Problem(path, index, message, line))
    return problems


def check_removed_legacy_files() -> list[Problem]:
    removed_files = (
        "src/app_context.py",
        "src/ui/page_dependencies.py",
        "src/ui/page_method_dispatch.py",
        "src/ui/page_contracts.py",
        "src/ui/page_signals",
        "src/ui/window_display_state.py",
        "src/ui/window_signal_bindings.py",
        "src/ui/window_state_sync.py",
        "src/ui/state/main_window_state.py",
        "src/ui/state/app_runtime_state.py",
    )
    problems: list[Problem] = []
    for rel in removed_files:
        path = REPO_ROOT / rel
        if path.exists():
            problems.append(Problem(path, 1, "старый файл не должен возвращаться"))
    return problems


def check_no_app_context(files: list[Path]) -> list[Problem]:
    return _scan_lines(
        files,
        re.compile(r"\b(app_context|AppContext|build_app_context|install_app_context|require_page_app_context|_require_app_context)\b"),
        "старый app_context/helper не должен использоваться",
    )


def check_no_page_signal_layer(files: list[Path]) -> list[Problem]:
    return _scan_lines(
        files,
        re.compile(
            r"\b(page_signals|connect_lazy_page_signals|connect_window_page_signals|"
            r"connect_page_signals|PageSignal|window_signal_bindings|"
            r"window_bindings_connected|_window_page_signals_connected|"
            r"_page_signal_bootstrap_complete|lazy_signal_connections|"
            r"finalize_page_signal_bootstrap)\b"
        ),
        "старый page_signals/window_signal_bindings слой не должен использоваться",
    )


def check_no_window_level_state_subscriptions(files: list[Path]) -> list[Problem]:
    scopes = []
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel == "src/ui/window_state_binder.py":
            continue
        if rel.startswith("src/main/") or (
            rel.startswith("src/ui/window_") and rel.endswith(".py")
        ):
            scopes.append(path)

    return _scan_lines(
        scopes,
        re.compile(r"\.subscribe\s*\("),
        "подписка окна на store/state должна жить в отдельном ui/window_state_binder.py",
    )


def check_runtime_feedback_uses_ui_bridge(files: list[Path]) -> list[Problem]:
    scopes = [
        path
        for path in files
        if _under(path, "src/winws_runtime/runtime/", "src/app/feature_facades/runtime")
    ]
    return _scan_lines(
        scopes,
        re.compile(r"\b(?:notify_threadsafe|notify_runner_launch_error_threadsafe|set_status_callback)\b"),
        "runtime feedback должен идти через RuntimeEvents/RuntimeUiBridge, а не отдельный callback окна",
    )


def check_runtime_ui_bridge_is_feature_neutral() -> list[Problem]:
    path = SRC_ROOT / "ui" / "runtime_ui_bridge.py"
    if not path.exists():
        return [Problem(path, 1, "runtime_ui_bridge.py не найден")]
    return _scan_lines(
        [path],
        re.compile(r"\b(?:premium|dns|hosts|presets|preset_)\b", re.IGNORECASE),
        "runtime_ui_bridge должен быть нейтральным runtime -> UI мостом без feature-логики",
    )


def check_preset_display_state_not_in_window_layer(files: list[Path]) -> list[Problem]:
    scopes = []
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.startswith("src/main/") or (
            rel.startswith("src/ui/window_") and rel.endswith(".py")
        ):
            scopes.append(path)

    return _scan_lines(
        scopes,
        re.compile(
            r"\b(?:set_current_strategy_summary|resolve_profile_strategy_display_state|"
            r"ProfileStrategyDisplayState|from presets\.display_state|import presets\.display_state)\b"
        ),
        "profile/preset display state должен считаться в presets/display_state.py, а не в window/main",
    )


def check_window_state_sync_is_window_only() -> list[Problem]:
    path = SRC_ROOT / "main" / "window_state_sync.py"
    if not path.exists():
        return [Problem(path, 1, "main/window_state_sync.py не найден")]
    return _scan_lines(
        [path],
        re.compile(r"\b(?:app_runtime\.features|features\.|get_premium_state|subscription_manager)\b"),
        "window_state_sync.py должен применять состояние окна, а не ходить в feature-сервисы",
    )


def check_page_navigation_uses_page_host(files: list[Path]) -> list[Problem]:
    scopes = []
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel == "src/ui/page_host.py":
            continue
        if rel.startswith("src/main/") or rel.startswith("src/ui/"):
            scopes.append(path)

    return _scan_lines(
        scopes,
        re.compile(
            r"(?:\bstackedWidget\.(?:addWidget|setCurrentWidget|currentWidget)\b|"
            r"\bnavigationInterface\.setCurrentItem\b|"
            r"\bpage_stack_bootstrap_complete\s*=)"
        ),
        "page/navigation lifecycle должен идти через WindowPageHost/WindowUiSession",
    )


def check_main_window_not_business_container(files: list[Path]) -> list[Problem]:
    scopes = [
        path for path in files
        if _under(path, "src/main/", "src/ui/") or path.relative_to(REPO_ROOT).as_posix() == "src/tray.py"
    ]
    return _scan_lines(
        scopes,
        re.compile(
            r"\b(?:window|self|app)\."
            r"(?:app_context|ui_state_store|app_runtime_state|launch_controller|"
            r"launch_runtime|launch_runtime_api|process_monitor_manager|"
            r"subscription_manager|tray_manager)\b"
        ),
        "MainWindow/UI не должны хранить бизнес-сервис или старое состояние",
    )


def check_pages_have_explicit_dependencies(files: list[Path]) -> list[Problem]:
    page_roots = (
        "src/profile/ui/",
        "src/presets/ui/",
        "src/orchestra/ui/",
        "src/blockcheck/ui/",
        "src/dns/ui/",
        "src/hosts/ui/",
        "src/donater/ui/",
        "src/log/ui/",
        "src/telegram_proxy/ui/",
        "src/lists/ui/",
        "src/ui/pages/",
    )
    scopes = [path for path in files if _under(path, *page_roots)]
    return _scan_lines(
        scopes,
        re.compile(
            r"(?:window\.app_runtime|window\.app_context|window\.ui_state_store|"
            r"self\.window\(\)\.|require_page_app_context|_require_app_context|page_dependencies)"
        ),
        "страница не должна искать зависимости через окно/parent",
    )


def check_external_imports(files: list[Path]) -> list[Problem]:
    external_roots = (
        "src/main/",
        "src/ui/",
        "src/presets/ui/",
        "src/profile/ui/",
        "src/donater/ui/",
        "src/dns/ui/",
        "src/hosts/ui/",
        "src/blockcheck/ui/",
        "src/lists/ui/",
        "src/orchestra/ui/",
        "src/telegram_proxy/ui/",
        "src/updater/ui/",
        "src/log/ui/",
    )
    feature_names = (
        "autostart|blobs|blockcheck|diagnostics|dns|donater|hosts|lists|"
        "log|orchestra|presets|profile|settings\\.dpi|telegram_proxy|"
        "updater|winws_runtime"
    )
    internals = "commands|public|service|manager|worker|runtime"
    pattern = re.compile(
        rf"\b(?:from (?:{feature_names})\.(?:{internals})\b|"
        rf"import (?:{feature_names})\.(?:{internals})\b)"
    )
    scopes = [
        path for path in files
        if _under(path, *external_roots) or path.relative_to(REPO_ROOT).as_posix() == "src/tray.py"
    ]
    return _scan_lines(
        scopes,
        pattern,
        "внешний слой не должен импортировать внутренний feature API",
    )


def check_no_feature_internals_from_external(files: list[Path]) -> list[Problem]:
    external_roots = (
        "src/main/",
        "src/ui/",
        "src/presets/ui/",
        "src/profile/ui/",
        "src/donater/ui/",
        "src/dns/ui/",
        "src/hosts/ui/",
        "src/blockcheck/ui/",
        "src/lists/ui/",
        "src/orchestra/ui/",
        "src/telegram_proxy/ui/",
        "src/updater/ui/",
        "src/log/ui/",
    )
    scopes = [
        path for path in files
        if _under(path, *external_roots) or path.relative_to(REPO_ROOT).as_posix() == "src/tray.py"
    ]
    return _scan_lines(
        scopes,
        re.compile(
            r"(?:app_runtime\.features\.[a-z_]+\.(?:objects|commands|_.*)|"
            r"features\.[a-z_]+\.(?:manager|worker|service|store|objects|commands|_.*)|"
            r"getattr\([^\n]*(?:app_runtime|features|runtime_feature|presets_feature|"
            r"profile_feature|premium_feature|dns_feature|hosts_feature|logs_feature|telegram_proxy_feature))"
        ),
        "внешний слой не должен лезть во внутренности feature",
    )


def check_startup_coordinator_boundary() -> list[Problem]:
    path = SRC_ROOT / "main" / "startup_coordinator.py"
    if not path.exists():
        return [Problem(path, 1, "startup_coordinator.py не найден")]
    return _scan_lines(
        [path],
        re.compile(r"\bself\.(?:app|window|app_runtime)\b"),
        "StartupCoordinator не должен держать всё окно или весь AppRuntime",
    )


def check_runtime_state_writers(files: list[Path]) -> list[Problem]:
    allowed = {
        "src/app/state_store.py",
        "src/winws_runtime/state/launch_runtime_service.py",
    }
    pattern = re.compile(
        r"\b(?:update|replace|setattr)\s*\([^)]*(?:launch_phase|launch_running|"
        r"launch_busy|launch_busy_text|launch_last_error)"
    )
    return _scan_lines(
        files,
        pattern,
        "runtime-state DPI должен записываться только через state_store/LaunchRuntimeService",
        allowed_paths=allowed,
    )


def check_blockcheck_runtime_boundary(files: list[Path]) -> list[Problem]:
    scopes = [path for path in files if _under(path, "src/blockcheck/")]
    return _scan_lines(
        scopes,
        re.compile(r"\b(?:from|import)\s+winws_runtime\.runners\b|winws_runtime\.runners\."),
        "blockcheck должен брать runtime-константы через winws_runtime.public, а не через runners",
    )


def check_premium_public_boundary() -> list[Problem]:
    path = SRC_ROOT / "donater" / "public.py"
    if not path.exists():
        return [Problem(path, 1, "donater/public.py не найден")]
    return _scan_lines(
        [path],
        re.compile(r"\b(?:PremiumCheckerBundle|get_premium_checker|resolve_checker_bundle|SubscriptionManager|storage)\b"),
        "donater.public не должен экспортировать внутренний Premium checker/storage/manager",
    )


def check_page_deps_builder_coverage() -> list[Problem]:
    schema_path = SRC_ROOT / "ui" / "navigation" / "schema.py"
    composition_path = SRC_ROOT / "ui" / "page_composition.py"
    if not schema_path.exists():
        return [Problem(schema_path, 1, "navigation schema не найден")]
    if not composition_path.exists():
        return [Problem(composition_path, 1, "page_composition.py не найден")]

    route_pages = _page_name_dict_keys(schema_path, "PAGE_ROUTE_SPECS")
    deps_pages = _page_name_dict_keys(composition_path, "PAGE_DEPS_BUILDERS")
    missing = sorted(route_pages - deps_pages)
    if not missing:
        return []
    return [
        Problem(
            composition_path,
            1,
            "для каждой route-страницы нужен явный builder зависимостей",
            ", ".join(missing),
        )
    ]


def check_translated_pages_require_deps() -> list[Problem]:
    targets = (
        (
            SRC_ROOT / "dns" / "ui" / "page.py",
            re.compile(r"def __init__\(self, parent=None, \*, dns_feature\)"),
            "NetworkPage должен принимать deps, а не dns_feature",
        ),
        (
            SRC_ROOT / "hosts" / "ui" / "page.py",
            re.compile(r"def __init__\(self, parent=None, \*, hosts_feature\)"),
            "HostsPage должен принимать deps, а не hosts_feature",
        ),
        (
            SRC_ROOT / "donater" / "ui" / "page.py",
            re.compile(r"def __init__\(self, parent=None, \*, (?:premium_feature|subscription_state_store)"),
            "PremiumPage должен принимать deps, а не premium_feature/subscription_state_store",
        ),
    )
    problems: list[Problem] = []
    for path, pattern, message in targets:
        if not path.exists():
            problems.append(Problem(path, 1, "переведённая страница не найдена"))
            continue
        problems.extend(_scan_lines([path], pattern, message))
    return problems


def check_translated_pages_have_no_command_signals() -> list[Problem]:
    page_paths = (
        SRC_ROOT / "dns" / "ui" / "page.py",
        SRC_ROOT / "hosts" / "ui" / "page.py",
        SRC_ROOT / "donater" / "ui" / "page.py",
    )
    return _scan_lines(
        [path for path in page_paths if path.exists()],
        re.compile(
            r"\b(?:start|stop|apply|refresh|open|switch|reset|create|check|activate|"
            r"start_dpi|stop_dpi|apply_dns|apply_hosts|refresh_subscription|"
            r"open_profile|open_preset)[a-z_]*\s*=\s*pyqtSignal\b"
        ),
        "переведённая страница не должна объявлять command-сигнал вместо deps",
    )


def check_pages_have_no_command_request_signals(files: list[Path]) -> list[Problem]:
    page_roots = (
        "src/profile/ui/",
        "src/presets/ui/",
        "src/orchestra/ui/",
        "src/blockcheck/ui/",
        "src/dns/ui/",
        "src/hosts/ui/",
        "src/donater/ui/",
        "src/log/ui/",
        "src/telegram_proxy/ui/",
        "src/lists/ui/",
        "src/ui/pages/",
        "src/updater/ui/",
    )
    scopes = [path for path in files if _under(path, *page_roots)]
    return _scan_lines(
        scopes,
        re.compile(
            r"\b(?:start|stop|apply|refresh|check|activate|switch|reset|create|"
            r"delete|remove|save|clear|flush|install|download|update|restart|run)"
            r"[a-z_]*_requested\s*=\s*pyqtSignal\b"
        ),
        "команда страницы должна идти через feature/deps/callback, а не через request-сигнал",
    )


def check_pages_have_no_navigation_request_signals(files: list[Path]) -> list[Problem]:
    page_roots = (
        "src/profile/ui/",
        "src/presets/ui/",
        "src/orchestra/ui/",
        "src/blockcheck/ui/",
        "src/dns/ui/",
        "src/hosts/ui/",
        "src/donater/ui/",
        "src/log/ui/",
        "src/telegram_proxy/ui/",
        "src/lists/ui/",
        "src/ui/pages/",
        "src/updater/ui/",
    )
    scopes = [path for path in files if _under(path, *page_roots)]
    return _scan_lines(
        scopes,
        re.compile(
            r"\b(?:open_[a-z_]+_requested|navigate_[a-z_]+_requested|"
            r"back_clicked|profile_setup_[a-z_]*requested|"
            r"preset_raw_editor_[a-z_]*requested|user_presets_[a-z_]*requested)"
            r"\s*=\s*pyqtSignal\b"
        ),
        "навигация страницы должна идти через callback/deps из page_composition, а не через request-сигнал",
    )


def run_checks() -> list[Problem]:
    files = _python_files()
    problems: list[Problem] = []
    problems.extend(check_removed_legacy_files())
    problems.extend(check_no_app_context(files))
    problems.extend(check_no_page_signal_layer(files))
    problems.extend(check_no_window_level_state_subscriptions(files))
    problems.extend(check_runtime_feedback_uses_ui_bridge(files))
    problems.extend(check_runtime_ui_bridge_is_feature_neutral())
    problems.extend(check_preset_display_state_not_in_window_layer(files))
    problems.extend(check_window_state_sync_is_window_only())
    problems.extend(check_page_navigation_uses_page_host(files))
    problems.extend(check_main_window_not_business_container(files))
    problems.extend(check_pages_have_explicit_dependencies(files))
    problems.extend(check_external_imports(files))
    problems.extend(check_no_feature_internals_from_external(files))
    problems.extend(check_startup_coordinator_boundary())
    problems.extend(check_runtime_state_writers(files))
    problems.extend(check_blockcheck_runtime_boundary(files))
    problems.extend(check_premium_public_boundary())
    problems.extend(check_page_deps_builder_coverage())
    problems.extend(check_translated_pages_require_deps())
    problems.extend(check_translated_pages_have_no_command_signals())
    problems.extend(check_pages_have_no_command_request_signals(files))
    problems.extend(check_pages_have_no_navigation_request_signals(files))
    return problems


def main() -> int:
    problems = run_checks()
    if problems:
        print("Architecture boundary check failed:")
        for problem in problems:
            print(problem.format())
        return 1
    print("Architecture boundary check passed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
