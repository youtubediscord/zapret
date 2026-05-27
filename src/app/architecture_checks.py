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


def check_no_app_runtime_context(files: list[Path]) -> list[Problem]:
    return _scan_lines(
        files,
        re.compile(r"\b(?:app_runtime|AppRuntime|window\.app_runtime|page\.window\(\)\.app_runtime)\.context\b"),
        "AppRuntime.context нельзя добавлять как новый общий app_context",
    )


def check_app_features_is_registry_only() -> list[Problem]:
    path = SRC_ROOT / "app" / "features.py"
    if not path.exists():
        return [Problem(path, 1, "app/features.py не найден")]
    return _scan_lines(
        [path],
        re.compile(r"\b(?:def\s+build_app_features|build_[a-z_]+feature|build_[a-z_]+_feature)\b"),
        "app/features.py должен быть registry dataclass; сборка feature живёт в app/feature_assembly.py",
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
        re.compile(
            r"\b(?:premium|dns|hosts|presets|preset_|WindowUiSession|"
            r"get_window_ui_session|app_runtime|window\.)\b",
            re.IGNORECASE,
        ),
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
        re.compile(
            r"\b(?:app_runtime\.features|features\.|get_premium_state|subscription_manager|"
            r"load_premium_effects|init_holiday_effects_from_settings|load_background_preset|"
            r"load_mica_enabled|HolidayEffectsManager|apply_aero_effect|apply_window_background)\b"
        ),
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
            r"(?:app_context|app_runtime_state|launch_controller|"
            r"launch_runtime|launch_runtime_api|process_monitor_manager|"
            r"subscription_manager|tray_manager)\b"
        ),
        "MainWindow/UI не должны хранить бизнес-сервис или старое состояние",
    )


def check_window_not_store_access_point(files: list[Path]) -> list[Problem]:
    scopes = []
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.startswith("src/main/window") or (
            rel.startswith("src/ui/window_") and rel.endswith(".py")
        ):
            scopes.append(path)

    return _scan_lines(
        scopes,
        re.compile(
            r"(?:\b(?:window|self|app)\._app_runtime_state\b|"
            r"\bdef\s+_?app_runtime_state\b)"
        ),
        "окно не должно возвращать старый app_runtime_state access point",
    )


def check_window_does_not_build_app_runtime() -> list[Problem]:
    scopes = [
        SRC_ROOT / "main" / "window.py",
        SRC_ROOT / "main" / "window_startup.py",
    ]
    return _scan_lines(
        [path for path in scopes if path.exists()],
        re.compile(r"\b(?:from app\.runtime import build_app_runtime|build_app_runtime\s*\()"),
        "главное окно не должно собирать AppRuntime; это делает ApplicationController",
    )


def check_window_has_no_bootstrap_wrapper() -> list[Problem]:
    scopes = [
        SRC_ROOT / "main" / "window.py",
        SRC_ROOT / "main" / "window_startup.py",
    ]
    return _scan_lines(
        [path for path in scopes if path.exists()],
        re.compile(r"\bdef\s+window_bootstrap"),
        "создание окна должно идти напрямую через ApplicationController",
    )


def check_app_runtime_access_is_narrow(files: list[Path]) -> list[Problem]:
    scopes = [
        path for path in files
        if _under(path, "src/main/", "src/ui/")
    ]
    return _scan_lines(
        scopes,
        re.compile(r"\b(?:self|window)\.app_runtime\b"),
        "окно не должно хранить AppRuntime; передавайте нужные зависимости явно",
    )


def check_window_feature_aliases_not_used(files: list[Path]) -> list[Problem]:
    scopes = []
    for path in files:
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel.startswith("src/main/window") or rel.startswith("src/ui/window_"):
            scopes.append(path)

    return _scan_lines(
        scopes,
        re.compile(
            r"\b(?:self|window)\."
            r"(?:runtime_feature|premium_feature|presets_feature|profile_feature|"
            r"dns_feature|hosts_feature|lists_feature|telegram_proxy_feature|"
            r"tray_feature|updater_feature|orchestra_feature)\b"
        ),
        "окно не должно хранить feature как свои поля; используйте явные deps",
    )


def check_window_hidden_dependency_bags_not_used(files: list[Path]) -> list[Problem]:
    scopes = [
        path for path in files
        if _under(path, "src/main/window", "src/ui/window_")
    ]
    return _scan_lines(
        scopes,
        re.compile(
            r"\b(?:WindowStartupDeps|WindowStateSyncDeps|"
            r"attach_window_[a-z_]+deps|_window_[a-z_]+deps)\b"
        ),
        "окно не должно хранить скрытые deps-контейнеры; подключайте явные callbacks/объекты из сборочного слоя",
    )


def check_tray_uses_window_port() -> list[Problem]:
    scopes = [
        SRC_ROOT / "tray.py",
        SRC_ROOT / "tray_commands.py",
        SRC_ROOT / "main" / "tray_window_port.py",
    ]
    existing_scopes = [path for path in scopes if path.exists()]
    if not existing_scopes:
        return []
    return _scan_lines(
        existing_scopes,
        re.compile(
            r"\b(?:def __init__\(self,\s*parent|self\.parent|"
            r"parent\s*=\s*(?:host|qt_parent|window)|"
            r"window_port\.qt_parent\s*\(|def\s+qt_parent\s*\()\b"
        ),
        "SystemTrayManager должен работать через методы TrayWindowPort, а не получать главное окно/qt_parent наружу",
    )


def check_window_runtime_setup_is_thin() -> list[Problem]:
    path = SRC_ROOT / "main" / "window_runtime_setup.py"
    if not path.exists():
        return []
    return _scan_lines(
        [path],
        re.compile(
            r"\b(?:"
            r"WindowNotificationCenter|WindowGeometryRuntime|WindowCloseFlow|"
            r"ApplicationLifecycle|PageDepsContext|WindowUiRoot|"
            r"on_open_profile_setup|on_background_refresh_needed|show_active_mode_control_page"
            r")\b"
        ),
        "window_runtime_setup.py должен быть тонким координатором; подробная сборка живёт в отдельных setup-файлах",
    )


def check_window_feature_deps_use_explicit_port() -> list[Problem]:
    path = SRC_ROOT / "main" / "window_feature_deps.py"
    if not path.exists():
        return [Problem(path, 1, "window_feature_deps.py не найден")]
    return _scan_lines(
        [path],
        re.compile(
            r"(?:def\s+build_window_feature_deps\s*\(\s*window\s*(?:,|\))|"
            r"\bwindow\.|getattr\(\s*window\b)"
        ),
        "window_feature_deps.py должен строиться из FeatureWindowDeps, а не вытаскивать зависимости из полного окна",
    )


def check_application_controller_uses_port_builders() -> list[Problem]:
    path = SRC_ROOT / "main" / "application_controller.py"
    if not path.exists():
        return [Problem(path, 1, "application_controller.py не найден")]
    return _scan_lines(
        [path],
        re.compile(r"\bFeatureWindowDeps\s*\("),
        "ApplicationController не должен вручную собирать FeatureWindowDeps из window; используйте отдельный port builder",
    )


def check_window_page_actions_is_callback_bag() -> list[Problem]:
    path = SRC_ROOT / "main" / "window_page_actions.py"
    if not path.exists():
        return [Problem(path, 1, "window_page_actions.py не найден")]
    return _scan_lines(
        [path],
        re.compile(r"(?:^\s*window\s*:|\bself\.window\b|\bpage_actions\.window\b|\bpage_actions\.appearance_actions\b)"),
        "WindowPageActions не должен хранить полное окно; он должен быть набором явных callback-ов",
    )


def check_application_lifecycle_uses_window_port() -> list[Problem]:
    path = SRC_ROOT / "main" / "application_lifecycle.py"
    if not path.exists():
        return [Problem(path, 1, "application_lifecycle.py не найден")]
    return _scan_lines(
        [path],
        re.compile(r"(?:^\s*window\s*,|\bself\._window\s*=|\bself\._window\b)"),
        "ApplicationLifecycle не должен хранить главное окно напрямую; используйте lifecycle window port",
    )


def check_window_page_deps_setup_uses_actions() -> list[Problem]:
    path = SRC_ROOT / "main" / "window_page_deps_setup.py"
    if not path.exists():
        return [Problem(path, 1, "window_page_deps_setup.py не найден")]
    return _scan_lines(
        [path],
        re.compile(
            r"(?:build_window_page_deps_context\s*\(\s*window\s*(?:,|\))|"
            r"\bwindow\.(?:set_status|window_notification_center|app_runtime|ui_state_store|"
            r"runtime_feature|premium_feature|presets_feature|profile_feature|dns_feature|"
            r"hosts_feature|lists_feature|telegram_proxy_feature|tray_feature|updater_feature|"
            r"orchestra_feature)\b|"
            r"from ui\.(?:workflows|profile_setup_workflow|window_appearance_state))"
        ),
        "window_page_deps_setup.py должен получать callbacks через WindowPageActions, а не доставать их из окна",
    )


def check_post_startup_uses_explicit_host(files: list[Path]) -> list[Problem]:
    scopes = [
        path for path in files
        if path.relative_to(REPO_ROOT).as_posix().startswith("src/main/post_startup")
        or path.relative_to(REPO_ROOT).as_posix() == "src/main/application_post_startup.py"
    ]
    return _scan_lines(
        scopes,
        re.compile(
            r"(?:startup_host\s*=\s*window\b|"
            r"\bis_window_alive\b|"
            r"\bstartup_host\.qt_parent\s*\(|"
            r"\bdef\s+qt_parent\s*\(|"
            r"\b(?:window|startup_host)\.[a-z_]+_feature\b)"
        ),
        "post-startup задачи должны получать PostStartupHost и явные deps, а не окно как контейнер feature",
    )


def check_discord_tray_command_does_not_receive_window() -> list[Problem]:
    scopes = [
        SRC_ROOT / "tray.py",
        SRC_ROOT / "tray_commands.py",
        SRC_ROOT / "discord" / "discord_restart.py",
        SRC_ROOT / "app" / "feature_facades" / "tray.py",
    ]
    return _scan_lines(
        [path for path in scopes if path.exists()],
        re.compile(r"toggle_discord_restart\s*\([^)]*(?:qt_parent|window_port|window|host|parent)"),
        "Discord tray command не должен получать главное окно/Qt-parent; это отдельная команда настройки",
    )


def check_post_startup_does_not_use_window_as_feature_container() -> list[Problem]:
    path = SRC_ROOT / "main" / "post_startup.py"
    if not path.exists():
        return []
    return _scan_lines(
        [path],
        re.compile(r"\b(?:window|startup_host)\.[a-z_]+_feature\b|def\s+build_post_startup_deps\s*\("),
        "post_startup.py должен получать готовые PostStartupDeps, а не доставать feature из окна",
    )


def check_page_deps_context_not_stored_on_window(files: list[Path]) -> list[Problem]:
    scopes = [
        path for path in files
        if _under(path, "src/main/", "src/ui/")
    ]
    return _scan_lines(
        scopes,
        re.compile(
            r"(?:\bwindow\.page_deps_context\b|"
            r"\bself\.page_deps_context\b|"
            r"getattr\([^)]*page_deps_context)"
        ),
        "PageDepsContext должен передаваться в UiPageFactory/WindowUiRoot явно, а не храниться на окне",
    )


def check_no_qfluentwidgets_fallbacks(files: list[Path]) -> list[Problem]:
    ui_roots = (
        "src/ui/",
        "src/presets/ui/",
        "src/profile/ui/",
        "src/updater/ui/",
        "src/hosts/ui/",
        "src/dns/ui/",
        "src/donater/ui/",
        "src/lists/ui/",
        "src/blockcheck/ui/",
        "src/blobs/ui/",
        "src/autostart/ui/",
        "src/settings/dpi/",
        "src/orchestra/ui/",
    )
    scopes = [
        path for path in files
        if _under(path, *ui_roots) or path.relative_to(REPO_ROOT).as_posix() == "src/tray.py"
    ]
    fluent_flags = "|".join(
        re.escape(value)
        for value in (
            "HAS_" + "FLUENT",
            "_HAS_" + "FLUENT",
            "_USE_" + "FLUENT",
        )
    )
    return _scan_lines(
        scopes,
        re.compile(
            rf"\b(?:{fluent_flags})\b|"
            r"BreadcrumbBar\s*=\s*None|"
            r"except\s+ImportError\s*:"
        ),
        "production UI должен требовать qfluentwidgets, а не уходить в обычный Qt fallback",
    )


def check_no_legacy_toggle_widgets_in_production_ui(files: list[Path]) -> list[Problem]:
    ui_roots = (
        "src/ui/",
        "src/presets/ui/",
        "src/profile/ui/",
        "src/updater/ui/",
        "src/hosts/ui/",
        "src/dns/ui/",
        "src/donater/ui/",
        "src/lists/ui/",
        "src/blockcheck/ui/",
        "src/blobs/ui/",
        "src/autostart/ui/",
        "src/settings/dpi/",
        "src/orchestra/ui/",
    )
    scopes = [
        path for path in files
        if _under(path, *ui_roots)
    ]
    return _scan_lines(
        scopes,
        re.compile(
            r"(?:from\s+PyQt6\.QtWidgets\s+import[^\n]*\bQCheckBox\b|"
            r"\bQCheckBox\b|"
            r"\bWin11ToggleSwitch\b|"
            r"\bcheckbox_cls\s*=\s*QCheckBox\b)"
        ),
        "production UI должен использовать stock qfluentwidgets toggle/check widgets, а не QCheckBox/Win11ToggleSwitch",
    )


def check_no_raw_text_edit_in_production_ui(files: list[Path]) -> list[Problem]:
    ui_roots = (
        "src/ui/",
        "src/presets/ui/",
        "src/profile/ui/",
        "src/updater/ui/",
        "src/hosts/ui/",
        "src/dns/ui/",
        "src/donater/ui/",
        "src/lists/ui/",
        "src/blockcheck/ui/",
        "src/blobs/ui/",
        "src/autostart/ui/",
        "src/settings/dpi/",
        "src/orchestra/ui/",
        "src/log/ui/",
        "src/telegram_proxy/ui/",
    )
    scopes = [
        path for path in files
        if _under(path, *ui_roots)
    ]
    return _scan_lines(
        scopes,
        re.compile(
            r"(?:from\s+PyQt6\.QtWidgets\s+import[^\n]*\bQTextEdit\b|"
            r"\bQTextEdit\s*\(|"
            r"\bqtextedit_cls\s*=\s*QTextEdit\b)"
        ),
        "production UI должен использовать проектную fluent-обёртку TextEdit, например ScrollBlockingTextEdit, а не обычный QTextEdit",
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


def check_ui_state_store_writer_ownership(files: list[Path]) -> list[Problem]:
    rules: tuple[tuple[re.Pattern[str], str, set[str]], ...] = (
        (
            re.compile(r"\.set_launch_busy\s*\("),
            "launch busy state должен писать только LaunchRuntimeService",
            {"src/winws_runtime/state/launch_runtime_service.py"},
        ),
        (
            re.compile(r"\.set_subscription\s*\("),
            "Premium state должен писать только Premium/Subscription слой",
            {"src/donater/subscription_ui.py"},
        ),
        (
            re.compile(r"\.set_current_strategy_summary\s*\("),
            "current strategy summary должен писать только presets/display_state.py",
            {"src/presets/display_state.py"},
        ),
        (
            re.compile(r"\.set_holiday_overlays\s*\("),
            "holiday overlay state должен писать только window_state_actions.py",
            {"src/main/window_state_actions.py"},
        ),
        (
            re.compile(r"\.set_window_opacity_value\s*\("),
            "window opacity state должен писать только window_state_actions.py",
            {"src/main/window_state_actions.py"},
        ),
        (
            re.compile(r"\.set_autostart\s*\("),
            "autostart state должен писать только autostart feature/AppRuntimeState",
            {"src/app/feature_facades/autostart.py", "src/app/state_store.py"},
        ),
        (
            re.compile(r"\.bump_active_preset_revision\b"),
            "active preset revision должен писать только preset runtime coordinator",
            {"src/core/runtime/preset_runtime_coordinator.py"},
        ),
        (
            re.compile(r"\.bump_preset_content_revision\b"),
            "preset content revision должен писать только preset runtime/runtime UI bridge setup",
            {"src/core/runtime/preset_runtime_coordinator.py", "src/ui/window_bootstrap_runtime.py"},
        ),
        (
            re.compile(r"\.bump_preset_structure_revision\b"),
            "preset structure revision должен писать только presets UI subpage layer",
            {"src/presets/ui/common/preset_subpage_base.py"},
        ),
        (
            re.compile(r"\.bump_mode_revision\b"),
            "mode revision должен писать только runtime method switch flow",
            {"src/winws_runtime/runtime/method_switch_flow.py"},
        ),
    )

    problems: list[Problem] = []
    for pattern, message, allowed_paths in rules:
        problems.extend(
            _scan_lines(
                files,
                pattern,
                message,
                allowed_paths=allowed_paths,
            )
        )
    return problems


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


def check_page_composition_is_registry_only() -> list[Problem]:
    path = SRC_ROOT / "ui" / "page_composition.py"
    if not path.exists():
        return [Problem(path, 1, "page_composition.py не найден")]
    return _scan_lines(
        [path],
        re.compile(r"\b(?:def\s+build_.*page_kwargs|window\.app_runtime|runtime_parts)\b"),
        "page_composition.py должен быть общей картой; builder-ы живут в ui/page_deps",
    )


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


def check_nested_preset_pages_use_breadcrumbs() -> list[Problem]:
    scopes = [
        SRC_ROOT / "presets" / "ui" / "zapret1" / "user_presets_page.py",
        SRC_ROOT / "presets" / "ui" / "zapret2" / "user_presets_page.py",
        SRC_ROOT / "presets" / "ui" / "common" / "preset_subpage_base.py",
    ]
    forbidden_back_var = "back_" + "btn"
    forbidden_back_camel = "back" + "Button"
    forbidden_back_text = "Назад" + " к списку"
    forbidden_chevron = "chevron" + "-left"
    return _scan_lines(
        [path for path in scopes if path.exists()],
        re.compile(
            r"\b(?:"
            + re.escape(forbidden_back_var)
            + r"|"
            + re.escape(forbidden_back_camel)
            + r"|"
            + re.escape(forbidden_back_text)
            + r"|"
            + re.escape(forbidden_chevron)
            + r")\b"
        ),
        "вложенные preset-страницы должны использовать BreadcrumbBar, а не одиночную кнопку назад",
    )


def check_settings_json_is_single_app_storage(files: list[Path]) -> list[Problem]:
    problems: list[Problem] = []
    problems.extend(
        _scan_lines(
            files,
            re.compile(
                r"\b(?:"
                r"premium\.ini|user_hosts\.ini|post_activate|activation_key|RegistryWindowGeometryStore|"
                r"\.update_cache\.json|\.update_rate_limit\.json|\.server_pool_stats\.json|"
                r"\.selected_server\.json|\.github_cache\.json|\.github_rate_limit|"
                r"\.vps_block\.json|\.server_stats\.json|strategy_scan_resume\.json|"
                r"blockcheck_user_domains\.txt|blobs\.json"
                r")\b"
            ),
            "настройки/состояние приложения должны жить в settings.json; отдельные state-файлы запрещены",
        )
    )

    app_storage_scopes = [
        path
        for path in files
        if _under(path, "src/donater/", "src/hosts/", "src/settings/")
    ]
    problems.extend(
        _scan_lines(
            app_storage_scopes,
            re.compile(r"\b(?:ConfigParser|configparser)\b"),
            "для рабочих настроек приложения нельзя возвращать ini-парсер; используйте settings.json",
        )
    )
    return problems


def check_page_deps_context_has_explicit_fields(files: list[Path]) -> list[Problem]:
    scopes = [
        path for path in files
        if _under(path, "src/ui/page_deps/", "src/main/window_page_deps_setup.py")
    ]
    return _scan_lines(
        scopes,
        re.compile(
            r"\b(?:PageDepsContext|def\s+build_[a-z_]+_page_kwargs\s*\(\s*context\b|"
            r"context\.|features\s*:\s*object|state\s*:\s*object)\b"
        ),
        "page deps builder не должен получать общий context; зависимости страницы задаются через PageDepsSpec",
    )


def check_preset_switch_has_no_full_start_fallback() -> list[Problem]:
    path = SRC_ROOT / "winws_runtime" / "runtime" / "control_workers.py"
    if not path.exists():
        return [Problem(path, 1, "control_workers.py не найден")]
    return _scan_lines(
        [path],
        re.compile(r"\b(?:getattr\([^)]*switch_preset_file_fast|runner\.start_from_preset_file\s*\()"),
        "PresetSwitchWorker должен использовать только switch_preset_file_fast без fallback на полный запуск",
    )


def check_fast_switch_runners_do_not_call_full_start_pipeline() -> list[Problem]:
    targets = (
        (SRC_ROOT / "winws_runtime" / "runners" / "zapret1_runner.py", "Winws1StrategyRunner"),
        (SRC_ROOT / "winws_runtime" / "runners" / "zapret2_runner.py", "Winws2StrategyRunner"),
    )
    problems: list[Problem] = []
    for path, class_name in targets:
        if not path.exists():
            problems.append(Problem(path, 1, f"{path.name} не найден"))
            continue
        tree = ast.parse(path.read_text(encoding="utf-8", errors="replace"))
        runner = next(
            (
                node
                for node in ast.walk(tree)
                if isinstance(node, ast.ClassDef) and node.name == class_name
            ),
            None,
        )
        if runner is None:
            problems.append(Problem(path, 1, f"{class_name} не найден"))
            continue
        switch_method = next(
            (
                node
                for node in runner.body
                if isinstance(node, ast.FunctionDef) and node.name == "switch_preset_file_fast"
            ),
            None,
        )
        if switch_method is None:
            problems.append(Problem(path, getattr(runner, "lineno", 1), "switch_preset_file_fast не найден"))
            continue
        for node in ast.walk(switch_method):
            if isinstance(node, ast.Attribute) and node.attr == "_start_from_preset_file_locked":
                problems.append(
                    Problem(
                        path,
                        getattr(node, "lineno", getattr(switch_method, "lineno", 1)),
                        "switch_preset_file_fast не должен откатываться в полный start pipeline",
                        "_start_from_preset_file_locked",
                    )
                )
    return problems


def check_no_running_preset_pid_probe(files: list[Path]) -> list[Problem]:
    scopes = [
        path for path in files
        if _under(path, "src/winws_runtime/")
    ]
    return _scan_lines(
        scopes,
        re.compile(r"\bfind_running_preset_pid\b"),
        "проверка запущенного preset через @preset больше не соответствует текущему запуску args и не должна использоваться",
    )


def check_ui_workflows_do_not_call_page_methods(files: list[Path]) -> list[Problem]:
    scopes = [
        path for path in files
        if _under(path, "src/ui/workflows/")
    ]
    return _scan_lines(
        scopes,
        re.compile(r"\.(?:show_profile|set_preset_file_name|apply_profile_setup_change)\s*\("),
        "UI workflow не должен вызывать методы конкретной страницы; используйте явное WindowPageActions/page presenter действие",
    )


def check_launch_preparation_does_not_mutate_source_preset() -> list[Problem]:
    path = SRC_ROOT / "winws_runtime" / "flow" / "start_preparation.py"
    if not path.exists():
        return [Problem(path, 1, "start_preparation.py не найден")]
    return _scan_lines(
        [path],
        re.compile(r"\bpreset_path\.write_text\s*\("),
        "подготовка запуска не должна менять source preset; готовьте текст запуска в памяти",
    )


def check_no_runtime_launch_preset_files(files: list[Path]) -> list[Problem]:
    return _scan_lines(
        files,
        re.compile(r"\b(?:runtime[/\\]launch_presets|launch_presets|\.launch\.txt|_launch_preset_artifact)\b"),
        "source preset должен оставаться единственным состоянием выбранного preset; не создавайте runtime/*.launch.txt копии. Узкий winws2 @config-адаптер допустим только как временный файл запуска, если его путь не попадает в UI/настройки",
    )


def check_no_hidden_winws2_launch_normalization(files: list[Path]) -> list[Problem]:
    scopes = [
        path for path in files
        if _under(path, "src/winws_runtime/", "src/profile/")
    ]
    return _scan_lines(
        scopes,
        re.compile(
            r"\b(?:normalize_winws2_action_lines|normalize_out_range_action_lines|"
            r"applied_default_out_range|defaulted_profiles|repaired_profiles|"
            r"removed_placeholder_profiles|_OUT_RANGE_UNSIGNED_SIMPLE_RE|"
            r"sanitize_presets_before_launch|_ensure_lua_init_lines|strip_strategy_tags)\b"
        ),
        "winws2 preset перед запуском нельзя скрыто нормализовать; только проверка и явная ошибка",
    )


def run_checks() -> list[Problem]:
    files = _python_files()
    problems: list[Problem] = []
    problems.extend(check_removed_legacy_files())
    problems.extend(check_no_app_context(files))
    problems.extend(check_no_app_runtime_context(files))
    problems.extend(check_app_features_is_registry_only())
    problems.extend(check_no_page_signal_layer(files))
    problems.extend(check_no_window_level_state_subscriptions(files))
    problems.extend(check_runtime_feedback_uses_ui_bridge(files))
    problems.extend(check_runtime_ui_bridge_is_feature_neutral())
    problems.extend(check_preset_display_state_not_in_window_layer(files))
    problems.extend(check_window_state_sync_is_window_only())
    problems.extend(check_page_navigation_uses_page_host(files))
    problems.extend(check_main_window_not_business_container(files))
    problems.extend(check_window_not_store_access_point(files))
    problems.extend(check_window_does_not_build_app_runtime())
    problems.extend(check_window_has_no_bootstrap_wrapper())
    problems.extend(check_app_runtime_access_is_narrow(files))
    problems.extend(check_window_feature_aliases_not_used(files))
    problems.extend(check_window_hidden_dependency_bags_not_used(files))
    problems.extend(check_tray_uses_window_port())
    problems.extend(check_window_runtime_setup_is_thin())
    problems.extend(check_window_feature_deps_use_explicit_port())
    problems.extend(check_application_controller_uses_port_builders())
    problems.extend(check_window_page_actions_is_callback_bag())
    problems.extend(check_application_lifecycle_uses_window_port())
    problems.extend(check_window_page_deps_setup_uses_actions())
    problems.extend(check_post_startup_uses_explicit_host(files))
    problems.extend(check_discord_tray_command_does_not_receive_window())
    problems.extend(check_post_startup_does_not_use_window_as_feature_container())
    problems.extend(check_page_deps_context_not_stored_on_window(files))
    problems.extend(check_no_qfluentwidgets_fallbacks(files))
    problems.extend(check_no_legacy_toggle_widgets_in_production_ui(files))
    problems.extend(check_no_raw_text_edit_in_production_ui(files))
    problems.extend(check_pages_have_explicit_dependencies(files))
    problems.extend(check_external_imports(files))
    problems.extend(check_no_feature_internals_from_external(files))
    problems.extend(check_startup_coordinator_boundary())
    problems.extend(check_runtime_state_writers(files))
    problems.extend(check_ui_state_store_writer_ownership(files))
    problems.extend(check_blockcheck_runtime_boundary(files))
    problems.extend(check_premium_public_boundary())
    problems.extend(check_page_deps_builder_coverage())
    problems.extend(check_page_composition_is_registry_only())
    problems.extend(check_translated_pages_require_deps())
    problems.extend(check_translated_pages_have_no_command_signals())
    problems.extend(check_pages_have_no_command_request_signals(files))
    problems.extend(check_pages_have_no_navigation_request_signals(files))
    problems.extend(check_nested_preset_pages_use_breadcrumbs())
    problems.extend(check_settings_json_is_single_app_storage(files))
    problems.extend(check_page_deps_context_has_explicit_fields(files))
    problems.extend(check_preset_switch_has_no_full_start_fallback())
    problems.extend(check_fast_switch_runners_do_not_call_full_start_pipeline())
    problems.extend(check_no_running_preset_pid_probe(files))
    problems.extend(check_ui_workflows_do_not_call_page_methods(files))
    problems.extend(check_launch_preparation_does_not_mutate_source_preset())
    problems.extend(check_no_runtime_launch_preset_files(files))
    problems.extend(check_no_hidden_winws2_launch_normalization(files))
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
