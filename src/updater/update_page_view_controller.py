from __future__ import annotations

from dataclasses import dataclass


@dataclass(slots=True)
class UpdateStatusCardPlan:
    title: str
    subtitle: str
    button_text: str


@dataclass(slots=True)
class ServerRowPlan:
    server_text: str
    server_accent: bool
    status_text: str
    status_color: tuple[int, int, int]
    time_text: str
    extra_text: str


@dataclass(slots=True)
class UpdateChannelActionResult:
    ok: bool
    message: str


@dataclass(slots=True)
class UpdateStatusTransitionPlan:
    is_checking: bool
    state: str
    state_version: str
    state_source: str
    state_message: str
    state_elapsed: float
    icon_mode: str
    loading_mode: str
    stop_loading_text: str
    check_enabled: bool | None


@dataclass(slots=True)
class ChangelogUpdatePlan:
    mode: str
    is_downloading: bool
    icon_kind: str
    raw_version: str
    download_error_text: str
    title_text: str
    version_text: str
    install_text: str
    raw_changelog: str
    changelog_html: str
    changelog_visible: bool
    progress_visible: bool
    buttons_visible: bool
    close_visible: bool


@dataclass(slots=True)
class ChangelogDownloadStartPlan:
    mode: str
    is_downloading: bool
    icon_kind: str
    raw_version: str
    title_text: str
    version_text: str
    progress_label_text: str
    speed_label_text: str
    eta_label_text: str
    show_progress_bar: bool
    show_indeterminate: bool
    progress_visible: bool
    buttons_visible: bool
    close_visible: bool
    download_start_time: float
    last_bytes: int
    last_speed_time: float
    last_speed_bytes: int
    smoothed_speed: float
    download_percent: int
    download_done_bytes: int
    download_total_bytes: int
    download_speed_kb: float | None
    download_eta_seconds: float | None
    download_error_text: str


@dataclass(slots=True)
class ChangelogProgressPlan:
    mode: str
    show_progress_bar: bool
    hide_indeterminate: bool
    progress_value: int
    progress_label_text: str
    version_text: str
    speed_label_text: str
    eta_label_text: str
    download_percent: int
    download_done_bytes: int
    download_total_bytes: int
    last_bytes: int
    last_speed_time: float
    last_speed_bytes: int
    smoothed_speed: float
    download_speed_kb: float | None
    download_eta_seconds: float | None


@dataclass(slots=True)
class ChangelogTerminalPlan:
    mode: str
    is_downloading: bool
    title_text: str
    version_text: str
    progress_value: int
    progress_label_text: str
    speed_label_text: str
    eta_label_text: str
    progress_visible: bool
    buttons_visible: bool
    close_visible: bool
    install_text: str
    icon_kind: str
    title_color: str | None
    error_text: str


class UpdatePageViewController:
    @staticmethod
    def _tr(language: str, key: str, default: str) -> str:
        from ui.text_catalog import tr as tr_catalog

        return tr_catalog(key, language=language, default=default)

    @staticmethod
    def make_links_clickable(text: str, accent_hex: str) -> str:
        import re

        url_pattern = r'(https?://[^\s<>"\']+)'

        def replace_url(match):
            url = match.group(1)
            while url and url[-1] in '.,;:!?)':
                url = url[:-1]
            return f'<a href="{url}" style="color: {accent_hex};">{url}</a>'

        return re.sub(url_pattern, replace_url, text)

    @staticmethod
    def build_update_status_card_plan(
        *,
        state: str,
        version: str,
        source: str,
        message: str,
        elapsed: float,
        app_version: str,
        language: str,
    ) -> UpdateStatusCardPlan:
        from ui.text_catalog import tr as tr_catalog

        def tr(key: str, default: str) -> str:
            return tr_catalog(key, language=language, default=default)

        if state == "checking":
            return UpdateStatusCardPlan(
                title=tr("page.servers.update.title.checking", "Проверка обновлений..."),
                subtitle=tr("page.servers.update.subtitle.checking", "Подождите, идёт проверка серверов"),
                button_text=tr("page.servers.update.button.check", "Проверить обновления"),
            )
        if state == "available":
            return UpdateStatusCardPlan(
                title=tr("page.servers.update.title.available_template", "Доступно обновление v{version}").format(version=version),
                subtitle=tr(
                    "page.servers.update.subtitle.available",
                    "Установите обновление ниже или проверьте ещё раз",
                ),
                button_text=tr("page.servers.update.button.recheck", "ПРОВЕРИТЬ СНОВА"),
            )
        if state == "up_to_date":
            return UpdateStatusCardPlan(
                title=tr("page.servers.update.title.none", "Обновлений нет"),
                subtitle=tr(
                    "page.servers.update.subtitle.latest_template",
                    "Установлена последняя версия {version}",
                ).format(version=app_version),
                button_text=tr("page.servers.update.button.recheck", "ПРОВЕРИТЬ СНОВА"),
            )
        if state == "error":
            return UpdateStatusCardPlan(
                title=tr("page.servers.update.title.error", "Ошибка проверки"),
                subtitle=str(message or "")[:60],
                button_text=tr("page.servers.update.button.retry", "Повторить"),
            )
        if state == "found":
            return UpdateStatusCardPlan(
                title=tr("page.servers.update.title.found_template", "Найдено обновление v{version}").format(version=version),
                subtitle=tr("page.servers.update.subtitle.source_template", "Источник: {source}").format(source=source),
                button_text=tr("page.servers.update.button.recheck", "ПРОВЕРИТЬ СНОВА"),
            )
        if state == "download_error":
            return UpdateStatusCardPlan(
                title=tr("page.servers.update.title.download_error", "Ошибка загрузки"),
                subtitle=tr("page.servers.update.subtitle.try_again", "Попробуйте снова"),
                button_text=tr("page.servers.update.button.recheck", "ПРОВЕРИТЬ СНОВА"),
            )
        if state == "deferred":
            return UpdateStatusCardPlan(
                title=tr("page.servers.update.title.deferred_template", "Обновление v{version} отложено").format(version=version),
                subtitle=tr("page.servers.update.subtitle.recheck_hint", "Нажмите для повторной проверки"),
                button_text=tr("page.servers.update.button.recheck", "ПРОВЕРИТЬ СНОВА"),
            )
        if state == "checked_ago":
            mins_ago = int(max(float(elapsed or 0.0), 0.0) // 60)
            secs_ago = int(max(float(elapsed or 0.0), 0.0) % 60)
            if mins_ago > 0:
                subtitle = tr(
                    "page.servers.update.subtitle.checked_ago_min_sec_template",
                    "Проверено {minutes}м {seconds}с назад",
                ).format(minutes=mins_ago, seconds=secs_ago)
            else:
                subtitle = tr(
                    "page.servers.update.subtitle.checked_ago_sec_template",
                    "Проверено {seconds}с назад",
                ).format(seconds=secs_ago)
            return UpdateStatusCardPlan(
                title=tr("page.servers.update.title.default", "Проверка обновлений"),
                subtitle=subtitle,
                button_text=tr("page.servers.update.button.recheck", "ПРОВЕРИТЬ СНОВА"),
            )
        if state == "auto_on":
            return UpdateStatusCardPlan(
                title=tr("page.servers.update.title.default", "Проверка обновлений"),
                subtitle=tr("page.servers.update.subtitle.auto_on", "Автопроверка включена"),
                button_text=tr("page.servers.update.button.recheck", "ПРОВЕРИТЬ СНОВА"),
            )
        if state == "manual":
            return UpdateStatusCardPlan(
                title=tr("page.servers.update.title.default", "Проверка обновлений"),
                subtitle=tr("page.servers.update.subtitle.press_button", "Нажмите кнопку для проверки"),
                button_text=tr("page.servers.update.button.manual", "ПРОВЕРИТЬ ВРУЧНУЮ"),
            )
        return UpdateStatusCardPlan(
            title=tr("page.servers.update.title.default", "Проверка обновлений"),
            subtitle=tr(
                "page.servers.update.subtitle.default",
                "Нажмите для проверки доступных обновлений",
            ),
            button_text=tr("page.servers.update.button.check", "Проверить обновления"),
        )

    @staticmethod
    def build_server_row_plan(
        *,
        row_server_name: str,
        status: dict,
        channel: str,
        language: str,
    ) -> ServerRowPlan:
        from ui.text_catalog import tr as tr_catalog
        from updater.channel_utils import is_test_update_channel

        def tr(key: str, default: str) -> str:
            return tr_catalog(key, language=language, default=default)

        server_accent = bool(status.get("is_current"))
        server_text = f"⭐ {row_server_name}" if server_accent else row_server_name

        state = status.get("status")
        if state == "online":
            status_text = tr("page.servers.table.status.online", "● Онлайн")
            status_color = (134, 194, 132)
        elif state == "blocked":
            status_text = tr("page.servers.table.status.blocked", "● Блок")
            status_color = (230, 180, 100)
        elif state == "skipped":
            status_text = tr("page.servers.table.status.waiting", "● Ожидание")
            status_color = (160, 160, 160)
        else:
            status_text = tr("page.servers.table.status.offline", "● Офлайн")
            status_color = (220, 130, 130)

        if status.get("response_time"):
            time_text = tr("page.servers.table.time.ms_template", "{ms}мс").format(
                ms=f"{status.get('response_time', 0) * 1000:.0f}"
            )
        else:
            time_text = tr("page.servers.table.time.empty", "—")

        if row_server_name == "Telegram Bot":
            if status.get("status") == "online":
                if is_test_update_channel(channel):
                    extra_text = tr("page.servers.table.versions.test_template", "T: {version}").format(
                        version=status.get("test_version", "—")
                    )
                else:
                    extra_text = tr("page.servers.table.versions.stable_template", "S: {version}").format(
                        version=status.get("stable_version", "—")
                    )
            else:
                extra_text = str(status.get("error", ""))[:40]
        elif row_server_name == "GitHub API":
            if status.get("rate_limit") is not None:
                extra_text = tr("page.servers.table.versions.rate_limit_template", "Лимит: {remaining}/{limit}").format(
                    remaining=status["rate_limit"],
                    limit=status.get("rate_limit_max", 60),
                )
            else:
                extra_text = str(status.get("error", ""))[:40]
        elif status.get("status") == "online":
            extra_text = tr("page.servers.table.versions.both_template", "S: {stable}, T: {test}").format(
                stable=status.get("stable_version", "—"),
                test=status.get("test_version", "—"),
            )
        else:
            extra_text = str(status.get("error", ""))[:40]

        return ServerRowPlan(
            server_text=server_text,
            server_accent=server_accent,
            status_text=status_text,
            status_color=status_color,
            time_text=time_text,
            extra_text=extra_text,
        )

    @staticmethod
    def open_update_channel(channel: str) -> UpdateChannelActionResult:
        from config.telegram_links import open_telegram_link
        from updater.channel_utils import is_test_update_channel

        try:
            domain = "zapretguidev" if is_test_update_channel(channel) else "zapretnetdiscordyoutube"
            open_telegram_link(domain)
            return UpdateChannelActionResult(True, domain)
        except Exception as e:
            return UpdateChannelActionResult(False, str(e))

    @classmethod
    def build_update_status_transition_plan(
        cls,
        *,
        target_state: str,
        language: str,
        version: str = "",
        source: str = "",
        message: str = "",
        elapsed: float = 0.0,
        found_update: bool | None = None,
    ) -> UpdateStatusTransitionPlan:
        tr = lambda key, default: cls._tr(language, key, default)
        state = str(target_state or "").strip().lower()

        if state == "checking":
            return UpdateStatusTransitionPlan(
                is_checking=True,
                state="checking",
                state_version="",
                state_source="",
                state_message="",
                state_elapsed=0.0,
                icon_mode="idle",
                loading_mode="start",
                stop_loading_text="",
                check_enabled=None,
            )

        if state == "result":
            resolved_state = "available" if bool(found_update) else "up_to_date"
            return UpdateStatusTransitionPlan(
                is_checking=False,
                state=resolved_state,
                state_version=str(version or ""),
                state_source="",
                state_message="",
                state_elapsed=0.0,
                icon_mode="idle",
                loading_mode="stop",
                stop_loading_text=tr("page.servers.update.button.recheck", "ПРОВЕРИТЬ СНОВА"),
                check_enabled=None,
            )

        if state == "error":
            return UpdateStatusTransitionPlan(
                is_checking=False,
                state="error",
                state_version="",
                state_source="",
                state_message=str(message or "")[:60],
                state_elapsed=0.0,
                icon_mode="error",
                loading_mode="stop",
                stop_loading_text=tr("page.servers.update.button.retry", "Повторить"),
                check_enabled=None,
            )

        if state == "found":
            return UpdateStatusTransitionPlan(
                is_checking=False,
                state="found",
                state_version=str(version or ""),
                state_source=str(source or ""),
                state_message="",
                state_elapsed=0.0,
                icon_mode="idle",
                loading_mode="none",
                stop_loading_text="",
                check_enabled=True,
            )

        if state == "download_error":
            return UpdateStatusTransitionPlan(
                is_checking=False,
                state="download_error",
                state_version="",
                state_source="",
                state_message="",
                state_elapsed=0.0,
                icon_mode="error",
                loading_mode="none",
                stop_loading_text="",
                check_enabled=True,
            )

        if state == "deferred":
            return UpdateStatusTransitionPlan(
                is_checking=False,
                state="deferred",
                state_version=str(version or ""),
                state_source="",
                state_message="",
                state_elapsed=0.0,
                icon_mode="idle",
                loading_mode="none",
                stop_loading_text="",
                check_enabled=True,
            )

        if state == "checked_ago":
            return UpdateStatusTransitionPlan(
                is_checking=False,
                state="checked_ago",
                state_version="",
                state_source="",
                state_message="",
                state_elapsed=float(elapsed or 0.0),
                icon_mode="idle",
                loading_mode="none",
                stop_loading_text="",
                check_enabled=None,
            )

        if state == "auto_on":
            return UpdateStatusTransitionPlan(
                is_checking=False,
                state="auto_on",
                state_version="",
                state_source="",
                state_message="",
                state_elapsed=0.0,
                icon_mode="idle",
                loading_mode="none",
                stop_loading_text="",
                check_enabled=None,
            )

        if state == "manual":
            return UpdateStatusTransitionPlan(
                is_checking=False,
                state="manual",
                state_version="",
                state_source="",
                state_message="",
                state_elapsed=0.0,
                icon_mode="idle",
                loading_mode="none",
                stop_loading_text="",
                check_enabled=None,
            )

        return UpdateStatusTransitionPlan(
            is_checking=False,
            state="idle",
            state_version="",
            state_source="",
            state_message="",
            state_elapsed=0.0,
            icon_mode="idle",
            loading_mode="none",
            stop_loading_text="",
            check_enabled=None,
        )

    @classmethod
    def build_changelog_update_plan(
        cls,
        *,
        version: str,
        changelog: str,
        app_version: str,
        accent_hex: str,
        language: str,
    ) -> ChangelogUpdatePlan:
        tr = lambda key, default: cls._tr(language, key, default)

        clean_changelog = str(changelog or "")
        if clean_changelog and len(clean_changelog) > 200:
            clean_changelog = clean_changelog[:200] + "..."

        return ChangelogUpdatePlan(
            mode="update",
            is_downloading=False,
            icon_kind="update",
            raw_version=str(version or ""),
            download_error_text="",
            title_text=tr("page.servers.changelog.title.available", "Доступно обновление"),
            version_text=tr(
                "page.servers.changelog.version.transition_template",
                "v{current}  →  v{target}",
            ).format(current=app_version, target=version),
            install_text=tr("page.servers.changelog.button.install", "Установить"),
            raw_changelog=clean_changelog,
            changelog_html=cls.make_links_clickable(clean_changelog, accent_hex) if clean_changelog else "",
            changelog_visible=bool(clean_changelog),
            progress_visible=False,
            buttons_visible=True,
            close_visible=True,
        )

    @classmethod
    def build_changelog_download_start_plan(cls, *, version: str, language: str, now: float) -> ChangelogDownloadStartPlan:
        tr = lambda key, default: cls._tr(language, key, default)

        return ChangelogDownloadStartPlan(
            mode="downloading",
            is_downloading=True,
            icon_kind="download",
            raw_version=str(version or ""),
            title_text=tr("page.servers.changelog.title.downloading_template", "Загрузка v{version}").format(version=version),
            version_text=tr("page.servers.changelog.version.preparing", "Подготовка к загрузке..."),
            progress_label_text="0%",
            speed_label_text=tr("page.servers.changelog.progress.speed_unknown", "Скорость: —"),
            eta_label_text=tr("page.servers.changelog.progress.eta_unknown", "Осталось: —"),
            show_progress_bar=False,
            show_indeterminate=True,
            progress_visible=True,
            buttons_visible=False,
            close_visible=False,
            download_start_time=float(now),
            last_bytes=0,
            last_speed_time=float(now),
            last_speed_bytes=0,
            smoothed_speed=0.0,
            download_percent=0,
            download_done_bytes=0,
            download_total_bytes=0,
            download_speed_kb=None,
            download_eta_seconds=None,
            download_error_text="",
        )

    @classmethod
    def build_changelog_progress_plan(
        cls,
        *,
        percent: int,
        done_bytes: int,
        total_bytes: int,
        last_speed_time: float,
        last_speed_bytes: int,
        smoothed_speed: float,
        language: str,
        now: float,
        progress_bar_visible: bool,
    ) -> ChangelogProgressPlan:
        tr = lambda key, default: cls._tr(language, key, default)

        hide_indeterminate = not progress_bar_visible and done_bytes > 0
        show_progress_bar = progress_bar_visible or done_bytes > 0
        progress_label_text = f"{int(percent)}%"
        done_mb = done_bytes / (1024 * 1024)
        total_mb = total_bytes / (1024 * 1024)
        version_text = tr(
            "page.servers.changelog.progress.downloaded_mb_template",
            "Загружено {done:.1f} / {total:.1f} МБ",
        ).format(done=done_mb, total=total_mb)

        next_last_speed_time = float(last_speed_time)
        next_last_speed_bytes = int(last_speed_bytes)
        next_smoothed_speed = float(smoothed_speed)
        download_speed_kb: float | None = None
        download_eta_seconds: float | None = None
        speed_label_text = tr("page.servers.changelog.progress.speed_unknown", "Скорость: —")
        eta_label_text = tr("page.servers.changelog.progress.eta_unknown", "Осталось: —")

        dt = float(now) - float(last_speed_time)
        if dt >= 1.0 and done_bytes > 0:
            delta_bytes = int(done_bytes) - int(last_speed_bytes)
            if delta_bytes <= 0:
                next_smoothed_speed = 0.0
                next_last_speed_time = float(now)
                next_last_speed_bytes = int(done_bytes)
            else:
                instant_speed = delta_bytes / dt
                if next_smoothed_speed <= 0:
                    next_smoothed_speed = instant_speed
                else:
                    next_smoothed_speed = next_smoothed_speed * 0.4 + instant_speed * 0.6

                next_last_speed_time = float(now)
                next_last_speed_bytes = int(done_bytes)

                speed = next_smoothed_speed
                download_speed_kb = speed / 1024
                if download_speed_kb > 1024:
                    speed_label_text = tr(
                        "page.servers.changelog.progress.speed_mb_template",
                        "Скорость: {value:.1f} МБ/с",
                    ).format(value=download_speed_kb / 1024)
                else:
                    speed_label_text = tr(
                        "page.servers.changelog.progress.speed_kb_template",
                        "Скорость: {value:.0f} КБ/с",
                    ).format(value=download_speed_kb)

                if speed > 0:
                    remaining = (total_bytes - done_bytes) / speed
                    download_eta_seconds = remaining
                    if remaining < 60:
                        eta_label_text = tr(
                            "page.servers.changelog.progress.eta_sec_template",
                            "Осталось: {seconds} сек",
                        ).format(seconds=int(remaining))
                    else:
                        eta_label_text = tr(
                            "page.servers.changelog.progress.eta_min_template",
                            "Осталось: {minutes} мин",
                        ).format(minutes=int(remaining / 60))

        return ChangelogProgressPlan(
            mode="downloading",
            show_progress_bar=show_progress_bar,
            hide_indeterminate=hide_indeterminate,
            progress_value=int(percent),
            progress_label_text=progress_label_text,
            version_text=version_text,
            speed_label_text=speed_label_text,
            eta_label_text=eta_label_text,
            download_percent=int(percent),
            download_done_bytes=int(done_bytes),
            download_total_bytes=int(total_bytes),
            last_bytes=int(done_bytes),
            last_speed_time=next_last_speed_time,
            last_speed_bytes=next_last_speed_bytes,
            smoothed_speed=next_smoothed_speed,
            download_speed_kb=download_speed_kb,
            download_eta_seconds=download_eta_seconds,
        )

    @classmethod
    def build_changelog_terminal_plan(
        cls,
        *,
        kind: str,
        language: str,
        app_version: str,
        raw_version: str = "",
        download_error_text: str = "",
        download_done_bytes: int = 0,
        download_total_bytes: int = 0,
        download_percent: int = 0,
        download_speed_kb: float | None = None,
        download_eta_seconds: float | None = None,
    ) -> ChangelogTerminalPlan:
        tr = lambda key, default: cls._tr(language, key, default)

        if kind == "installing":
            return ChangelogTerminalPlan(
                mode="installing",
                is_downloading=False,
                title_text=tr("page.servers.changelog.title.installing", "Установка..."),
                version_text=tr(
                    "page.servers.changelog.version.installer_starting",
                    "Запуск установщика, приложение закроется",
                ),
                progress_value=100,
                progress_label_text="100%",
                speed_label_text="",
                eta_label_text="",
                progress_visible=True,
                buttons_visible=False,
                close_visible=False,
                install_text=tr("page.servers.changelog.button.install", "Установить"),
                icon_kind="download",
                title_color=None,
                error_text="",
            )

        if kind == "failed":
            return ChangelogTerminalPlan(
                mode="failed",
                is_downloading=False,
                title_text=tr("page.servers.changelog.title.download_error", "Ошибка загрузки"),
                version_text=(download_error_text[:80] if len(download_error_text) > 80 else download_error_text),
                progress_value=0,
                progress_label_text="",
                speed_label_text="",
                eta_label_text="",
                progress_visible=False,
                buttons_visible=True,
                close_visible=True,
                install_text=tr("page.servers.changelog.button.retry", "Повторить"),
                icon_kind="download_error",
                title_color="#ff6b6b",
                error_text=(download_error_text[:80] if len(download_error_text) > 80 else download_error_text),
            )

        if kind == "downloading":
            done_mb = download_done_bytes / (1024 * 1024)
            total_mb = download_total_bytes / (1024 * 1024)
            version_text = tr(
                "page.servers.changelog.progress.downloaded_mb_template",
                "Загружено {done:.1f} / {total:.1f} МБ",
            ).format(done=done_mb, total=total_mb) if download_done_bytes > 0 and download_total_bytes > 0 else tr(
                "page.servers.changelog.version.preparing",
                "Подготовка к загрузке...",
            )

            if download_speed_kb is None:
                speed_label_text = tr("page.servers.changelog.progress.speed_unknown", "Скорость: —")
            elif download_speed_kb > 1024:
                speed_label_text = tr(
                    "page.servers.changelog.progress.speed_mb_template",
                    "Скорость: {value:.1f} МБ/с",
                ).format(value=download_speed_kb / 1024)
            else:
                speed_label_text = tr(
                    "page.servers.changelog.progress.speed_kb_template",
                    "Скорость: {value:.0f} КБ/с",
                ).format(value=download_speed_kb)

            if download_eta_seconds is None:
                eta_label_text = tr("page.servers.changelog.progress.eta_unknown", "Осталось: —")
            elif download_eta_seconds < 60:
                eta_label_text = tr(
                    "page.servers.changelog.progress.eta_sec_template",
                    "Осталось: {seconds} сек",
                ).format(seconds=int(download_eta_seconds))
            else:
                eta_label_text = tr(
                    "page.servers.changelog.progress.eta_min_template",
                    "Осталось: {minutes} мин",
                ).format(minutes=int(download_eta_seconds / 60))

            return ChangelogTerminalPlan(
                mode="downloading",
                is_downloading=True,
                title_text=tr("page.servers.changelog.title.downloading_template", "Загрузка v{version}").format(
                    version=raw_version
                ),
                version_text=version_text,
                progress_value=int(download_percent),
                progress_label_text=f"{int(download_percent)}%",
                speed_label_text=speed_label_text,
                eta_label_text=eta_label_text,
                progress_visible=True,
                buttons_visible=False,
                close_visible=False,
                install_text=tr("page.servers.changelog.button.install", "Установить"),
                icon_kind="download",
                title_color=None,
                error_text="",
            )

        return ChangelogTerminalPlan(
            mode="update",
            is_downloading=False,
            title_text=tr("page.servers.changelog.title.available", "Доступно обновление"),
            version_text=tr(
                "page.servers.changelog.version.transition_template",
                "v{current}  →  v{target}",
            ).format(current=app_version, target=raw_version),
            progress_value=0,
            progress_label_text="",
            speed_label_text="",
            eta_label_text="",
            progress_visible=False,
            buttons_visible=True,
            close_visible=True,
            install_text=tr("page.servers.changelog.button.install", "Установить"),
            icon_kind="update",
            title_color=None,
            error_text="",
        )
