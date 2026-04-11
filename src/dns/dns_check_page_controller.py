from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class DNSCheckStartPlan:
    status_text: str
    status_tone: str
    disable_save: bool
    check_enabled: bool
    quick_enabled: bool
    save_enabled: bool
    progress_visible: bool


@dataclass(slots=True)
class DNSResultLinePlan:
    color_role: str


@dataclass(slots=True)
class DNSCheckFinishPlan:
    status_text: str
    status_tone: str
    enable_save: bool
    check_enabled: bool
    quick_enabled: bool
    save_enabled: bool
    progress_visible: bool


@dataclass(slots=True)
class DNSCheckCleanupPlan:
    should_quit_thread: bool
    wait_timeout_ms: int
    should_delete_thread: bool
    should_delete_worker: bool


@dataclass(slots=True)
class DNSQuickCheckPlan:
    lines: tuple[str, ...]
    enable_save: bool


@dataclass(slots=True)
class DNSSaveResultPlan:
    success: bool
    title: str
    content: str
    open_folder: str | None


class DNSCheckPageController:
    @staticmethod
    def create_worker():
        from .dns_check_worker import DNSCheckWorker

        return DNSCheckWorker()

    @staticmethod
    def build_start_plan() -> DNSCheckStartPlan:
        return DNSCheckStartPlan(
            status_text="🔄 Выполняется проверка DNS...",
            status_tone="accent",
            disable_save=True,
            check_enabled=False,
            quick_enabled=False,
            save_enabled=False,
            progress_visible=True,
        )

    @staticmethod
    def build_result_line_plan(text: str) -> DNSResultLinePlan:
        raw = str(text or "")
        if "✅" in raw:
            return DNSResultLinePlan(color_role="success")
        if "❌" in raw:
            return DNSResultLinePlan(color_role="error")
        if "⚠️" in raw:
            return DNSResultLinePlan(color_role="warning")
        if "🚫" in raw:
            return DNSResultLinePlan(color_role="blocked")
        if "🔍" in raw or "📊" in raw:
            return DNSResultLinePlan(color_role="accent")
        if "=" in raw and len(raw) > 20:
            return DNSResultLinePlan(color_role="faint")
        return DNSResultLinePlan(color_role="normal")

    @staticmethod
    def build_finish_plan(results: dict) -> DNSCheckFinishPlan:
        poisoning_detected = bool(results and results.get("summary", {}).get("dns_poisoning_detected"))
        if poisoning_detected:
            return DNSCheckFinishPlan(
                status_text="⚠️ Обнаружена DNS подмена!",
                status_tone="error",
                enable_save=True,
                check_enabled=True,
                quick_enabled=True,
                save_enabled=True,
                progress_visible=False,
            )
        return DNSCheckFinishPlan(
            status_text="✅ Проверка завершена",
            status_tone="success",
            enable_save=True,
            check_enabled=True,
            quick_enabled=True,
            save_enabled=True,
            progress_visible=False,
        )

    @staticmethod
    def build_cleanup_plan(*, has_thread: bool, has_worker: bool, thread_running: bool) -> DNSCheckCleanupPlan:
        return DNSCheckCleanupPlan(
            should_quit_thread=bool(has_thread and thread_running),
            wait_timeout_ms=500,
            should_delete_thread=bool(has_thread),
            should_delete_worker=bool(has_worker),
        )

    @staticmethod
    def run_quick_dns_check() -> DNSQuickCheckPlan:
        lines: list[str] = [
            "⚡ БЫСТРАЯ ПРОВЕРКА СИСТЕМНОГО DNS",
            "=" * 45,
            "",
        ]
        test_domains = {
            "YouTube": "www.youtube.com",
            "Discord": "discord.com",
            "Google": "google.com",
            "Cloudflare": "cloudflare.com",
        }

        all_ok = True
        for name, domain in test_domains.items():
            try:
                ip = socket.gethostbyname(domain)
                lines.append(f"✅ {name} ({domain}): {ip}")
            except Exception as e:
                lines.append(f"❌ {name} ({domain}): Ошибка - {e}")
                all_ok = False

        lines.append("")
        if all_ok:
            lines.append("✅ Все домены резолвятся корректно")
        else:
            lines.append("⚠️ Есть проблемы с резолвингом некоторых доменов")

        return DNSQuickCheckPlan(lines=tuple(lines), enable_save=True)

    @staticmethod
    def build_save_default_filename() -> str:
        return f"dns_check_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"

    @staticmethod
    def save_results_text(*, file_path: str, plain_text: str) -> DNSSaveResultPlan:
        target_path = str(file_path or "").strip()
        if not target_path:
            return DNSSaveResultPlan(
                success=False,
                title="Ошибка",
                content="Не указан путь для сохранения файла.",
                open_folder=None,
            )

        try:
            with open(target_path, "w", encoding="utf-8") as f:
                f.write("DNS CHECK RESULTS\n")
                f.write(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                f.write("=" * 60 + "\n\n")
                f.write(str(plain_text or ""))

            folder = os.path.dirname(target_path) or None
            if folder and hasattr(os, "startfile"):
                try:
                    os.startfile(folder)  # type: ignore[attr-defined]
                except Exception:
                    folder = None

            return DNSSaveResultPlan(
                success=True,
                title="Сохранено",
                content=f"Результаты сохранены в:\n{target_path}",
                open_folder=folder,
            )
        except Exception as e:
            return DNSSaveResultPlan(
                success=False,
                title="Ошибка",
                content=f"Не удалось сохранить файл:\n{str(e)}",
                open_folder=None,
            )
