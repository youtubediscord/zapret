"""Блокировка базового списка государственных СМИ РФ через Windows hosts."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from log.log import log


_BLOCK_BEGIN = "# >>> zapretgui:russian-state-media-block begin >>>"
_BLOCK_END = "# <<< zapretgui:russian-state-media-block end <<<"


@dataclass(frozen=True, slots=True)
class StateMediaDomainGroup:
    name: str
    domains: tuple[str, ...]


STATE_MEDIA_DOMAIN_GROUPS: tuple[StateMediaDomainGroup, ...] = (
    StateMediaDomainGroup("ТАСС", ("tass.ru", "www.tass.ru", "tass.com", "www.tass.com")),
    StateMediaDomainGroup("РИА Новости", ("ria.ru", "www.ria.ru")),
    StateMediaDomainGroup("Sputnik", ("radiosputnik.ru", "www.radiosputnik.ru", "sputnikglobe.com", "www.sputnikglobe.com")),
    StateMediaDomainGroup("RT", ("rt.com", "www.rt.com", "russian.rt.com")),
    StateMediaDomainGroup("ВГТРК", ("vgtrk.ru", "www.vgtrk.ru", "vesti.ru", "www.vesti.ru", "smotrim.ru", "www.smotrim.ru")),
    StateMediaDomainGroup("Российская газета", ("rg.ru", "www.rg.ru")),
    StateMediaDomainGroup("Парламентская газета", ("pnp.ru", "www.pnp.ru")),
    StateMediaDomainGroup("Звезда", ("tvzvezda.ru", "www.tvzvezda.ru")),
    StateMediaDomainGroup("Первый канал", ("1tv.ru", "www.1tv.ru", "1tv.com", "www.1tv.com")),
)


def get_state_media_domains() -> tuple[str, ...]:
    domains: list[str] = []
    seen: set[str] = set()
    for group in STATE_MEDIA_DOMAIN_GROUPS:
        for domain in group.domains:
            normalized = str(domain or "").strip().lower().strip(".")
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            domains.append(normalized)
    return tuple(domains)


def _remove_block(lines: list[str]) -> tuple[list[str], bool]:
    new_lines: list[str] = []
    inside_block = False
    removed = False
    for line in lines:
        if _BLOCK_BEGIN in line:
            inside_block = True
            removed = True
            continue
        if _BLOCK_END in line:
            inside_block = False
            removed = True
            continue
        if not inside_block:
            new_lines.append(line)
    return new_lines, removed


def _format_block(domains: tuple[str, ...]) -> list[str]:
    block = [
        _BLOCK_BEGIN + "\n",
        "# Базовый список государственных новостных сайтов РФ.\n",
    ]
    for domain in domains:
        block.append(f"127.0.0.1 {domain}\n")
        block.append(f"::1 {domain}\n")
    block.append(_BLOCK_END + "\n")
    return block


def build_hosts_content_with_state_media_block(content: str, *, enabled: bool) -> str:
    lines = str(content or "").splitlines(keepends=True)
    lines, _removed = _remove_block(lines)
    if enabled:
        if lines and not lines[-1].endswith(("\n", "\r")):
            lines[-1] += "\n"
        if lines and lines[-1].strip():
            lines.append("\n")
        lines.extend(_format_block(get_state_media_domains()))
    return "".join(lines)


class RussianStateMediaBlockerManager:
    """Меняет только собственный блок ZapretGUI в Windows hosts."""

    def __init__(
        self,
        status_callback: Callable[[str], None] | None = None,
        *,
        read_hosts_file: Callable[[], str | None] | None = None,
        write_hosts_file: Callable[[str], bool] | None = None,
    ) -> None:
        self._status_callback = status_callback or (lambda _message: None)
        self._read_hosts_file = read_hosts_file
        self._write_hosts_file = write_hosts_file

    def _set_status(self, message: str) -> None:
        self._status_callback(message)
        log(f"RussianStateMediaBlocker: {message}", "INFO")

    def _read_hosts(self) -> str | None:
        if self._read_hosts_file is not None:
            return self._read_hosts_file()
        from hosts.hosts import safe_read_hosts_file

        return safe_read_hosts_file()

    def _write_hosts(self, content: str) -> bool:
        if self._write_hosts_file is not None:
            return bool(self._write_hosts_file(content))
        from hosts.hosts import invalidate_hosts_file_cache, safe_write_hosts_file

        ok = bool(safe_write_hosts_file(content))
        if ok:
            invalidate_hosts_file_cache()
        return ok

    def is_blocked(self) -> bool:
        try:
            from settings.store import get_russian_state_media_blocked

            return bool(get_russian_state_media_blocked())
        except Exception:
            return False

    def set_blocked_memory(self, blocked: bool) -> bool:
        try:
            from settings.store import set_russian_state_media_blocked

            return bool(set_russian_state_media_blocked(bool(blocked)))
        except Exception as exc:
            log(f"Ошибка сохранения состояния блокировки государственных СМИ РФ: {exc}", "ERROR")
            return False

    def enable_blocking(self) -> tuple[bool, str]:
        self._set_status("Включение блокировки государственных СМИ РФ...")
        content = self._read_hosts()
        if content is None:
            return False, "Не удалось прочитать файл hosts."
        next_content = build_hosts_content_with_state_media_block(content, enabled=True)
        if not self._write_hosts(next_content):
            return False, "Не удалось записать файл hosts. Возможно, нужны права администратора."
        self.set_blocked_memory(True)
        count = len(get_state_media_domains())
        message = f"Блокировка государственных СМИ РФ включена. Добавлено доменов: {count}."
        self._set_status("Блокировка государственных СМИ РФ включена")
        return True, message

    def disable_blocking(self) -> tuple[bool, str]:
        self._set_status("Отключение блокировки государственных СМИ РФ...")
        content = self._read_hosts()
        if content is None:
            return False, "Не удалось прочитать файл hosts."
        next_content = build_hosts_content_with_state_media_block(content, enabled=False)
        if not self._write_hosts(next_content):
            return False, "Не удалось записать файл hosts. Возможно, нужны права администратора."
        self.set_blocked_memory(False)
        message = "Блокировка государственных СМИ РФ отключена. Записи ZapretGUI удалены из hosts."
        self._set_status("Блокировка государственных СМИ РФ отключена")
        return True, message


def is_state_media_blocked() -> bool:
    return RussianStateMediaBlockerManager().is_blocked()


def set_state_media_blocked(blocked: bool) -> bool:
    return RussianStateMediaBlockerManager().set_blocked_memory(blocked)


__all__ = [
    "RussianStateMediaBlockerManager",
    "STATE_MEDIA_DOMAIN_GROUPS",
    "build_hosts_content_with_state_media_block",
    "get_state_media_domains",
    "is_state_media_blocked",
    "set_state_media_blocked",
]
