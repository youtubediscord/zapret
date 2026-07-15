from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

from app.page_names import PageName
from app.ui_texts import (
    NAV_PAGE_TEXT_KEYS,
    TEXTS,
    _text_variants,
    get_nav_page_label,
    normalize_language,
    tr,
)
from settings.mode import ZAPRET1_MODE, ZAPRET2_MODE, normalize_launch_method


@dataclass(frozen=True)
class SearchEntry:
    entry_id: str
    page_name: PageName
    text_key: str = ""
    section_key: str | None = None
    tab_key: str | None = None
    keywords: tuple[str, ...] = ()
    text_prefixes: tuple[str, ...] = ()
    kind: str = "page"
    title: str = ""
    location: str = ""
    query_text: str = ""


@dataclass(frozen=True)
class SearchMatch:
    entry: SearchEntry
    score: int


SEARCH_ENTRIES: tuple[SearchEntry, ...] = (
    SearchEntry("winws2.control.title", PageName.ZAPRET2_MODE_CONTROL, "page.winws2_control.title"),
    SearchEntry("winws2.control.status", PageName.ZAPRET2_MODE_CONTROL, "page.control.status", section_key="page.control.status"),
    SearchEntry("winws2.control.preset", PageName.ZAPRET2_MODE_CONTROL, "page.winws2_control.preset_switch", section_key="page.winws2_control.preset_switch"),
    SearchEntry("winws2.control.mode", PageName.ZAPRET2_MODE_CONTROL, "page.winws2_control.profile_tuning", section_key="page.winws2_control.profile_tuning"),
    SearchEntry("winws2.mode.title", PageName.ZAPRET2_PRESET_SETUP, "page.winws2_pages.title"),
    SearchEntry("winws2.user_presets.title", PageName.ZAPRET2_USER_PRESETS, "page.winws2_user_presets.title"),
    SearchEntry("winws2.profile_setup.title", PageName.ZAPRET2_PROFILE_SETUP, "page.winws2_profile_setup.title"),
    SearchEntry("winws1.control.title", PageName.ZAPRET1_MODE_CONTROL, "page.winws1_control.title"),
    SearchEntry("winws1.control.presets", PageName.ZAPRET1_MODE_CONTROL, "page.winws1_control.presets", section_key="page.winws1_control.presets"),
    SearchEntry("winws1.mode.title", PageName.ZAPRET1_PRESET_SETUP, "page.winws1_pages.title"),
    SearchEntry("winws1.user_presets.title", PageName.ZAPRET1_USER_PRESETS, "page.winws1_user_presets.title"),
    SearchEntry("winws1.profile_setup.title", PageName.ZAPRET1_PROFILE_SETUP, "page.winws1_profile_setup.title"),
    SearchEntry("orchestra.title", PageName.ORCHESTRA, "page.orchestra.title"),
    SearchEntry("orchestra.training", PageName.ORCHESTRA, "page.orchestra.training_status", section_key="page.orchestra.training_status"),
    SearchEntry("orchestra.log", PageName.ORCHESTRA, "page.orchestra.log", section_key="page.orchestra.log"),
    SearchEntry("dpi.title", PageName.DPI_SETTINGS, "page.dpi_settings.title"),
    SearchEntry("dpi.launch_method", PageName.DPI_SETTINGS, "page.dpi_settings.launch_method", section_key="page.dpi_settings.launch_method"),
    SearchEntry("network.title", PageName.NETWORK, "page.network.title"),
    SearchEntry("network.dns", PageName.NETWORK, "page.network.dns", section_key="page.network.dns"),
    SearchEntry("network.adapters", PageName.NETWORK, "page.network.adapters", section_key="page.network.adapters"),
    SearchEntry("network.tools", PageName.NETWORK, "page.network.tools", section_key="page.network.tools"),
    SearchEntry("blockcheck.tab.blockcheck", PageName.BLOCKCHECK, "page.blockcheck.tab.blockcheck", section_key="nav.page.blockcheck", tab_key="blockcheck", text_prefixes=("page.blockcheck.",)),
    SearchEntry("blockcheck.tab.strategy_scan", PageName.BLOCKCHECK, "page.blockcheck.tab.strategy_scan", section_key="nav.page.blockcheck", tab_key="strategy_scan", text_prefixes=("page.strategy_scan.", "page.strategy_sort.")),
    SearchEntry("blockcheck.tab.diagnostics", PageName.BLOCKCHECK, "page.blockcheck.tab.diagnostics", section_key="nav.page.blockcheck", tab_key="diagnostics", text_prefixes=("page.connection.",)),
    SearchEntry("blockcheck.tab.dns_spoofing", PageName.BLOCKCHECK, "page.blockcheck.tab.dns_spoofing", section_key="nav.page.blockcheck", tab_key="dns_spoofing", text_prefixes=("page.dns_check.",)),
    SearchEntry("diag.tab.connection", PageName.BLOCKCHECK, "tab.diagnostics.connection", section_key="nav.page.blockcheck", tab_key="diagnostics"),
    SearchEntry("diag.tab.dns", PageName.BLOCKCHECK, "tab.diagnostics.dns", section_key="nav.page.blockcheck", tab_key="dns_spoofing"),
    SearchEntry("blockcheck.connection.title", PageName.BLOCKCHECK, "page.connection.title", section_key="page.blockcheck.tab.diagnostics", tab_key="diagnostics"),
    SearchEntry("blockcheck.dns_check.title", PageName.BLOCKCHECK, "page.dns_check.title", section_key="page.blockcheck.tab.dns_spoofing", tab_key="dns_spoofing"),
    SearchEntry("blockcheck.strategy_scan.title", PageName.BLOCKCHECK, "page.strategy_scan.title", section_key="page.blockcheck.tab.strategy_scan", tab_key="strategy_scan"),
    SearchEntry("blockcheck.strategy_sort.title", PageName.BLOCKCHECK, "page.strategy_sort.title", section_key="page.blockcheck.tab.strategy_scan", tab_key="strategy_scan"),
    SearchEntry("hosts.title", PageName.HOSTS, "page.hosts.title"),
    SearchEntry("hosts.services", PageName.HOSTS, "page.hosts.services", section_key="page.hosts.services"),
    SearchEntry("blockcheck.title", PageName.BLOCKCHECK, "page.blockcheck.title"),
    SearchEntry("blockcheck.monitoring", PageName.BLOCKCHECK, "page.blockcheck.monitoring", section_key="page.blockcheck.monitoring"),
    SearchEntry("appearance.title", PageName.APPEARANCE, "page.appearance.title"),
    SearchEntry("appearance.display_mode", PageName.APPEARANCE, "page.appearance.display_mode", section_key="page.appearance.display_mode"),
    SearchEntry("appearance.background", PageName.APPEARANCE, "page.appearance.background", section_key="page.appearance.background"),
    SearchEntry("premium.title", PageName.PREMIUM, "page.premium.title"),
    SearchEntry("premium.subscription", PageName.PREMIUM, "page.premium.subscription_status", section_key="page.premium.subscription_status"),
    SearchEntry("winws_log_analyzer.title", PageName.WINWS_LOG_ANALYZER, "page.winws_log_analyzer.title", keywords=("лог", "log", "winws2", "анализ")),
    SearchEntry("logs.title", PageName.LOGS, "page.logs.title"),
    SearchEntry("logs.controls", PageName.LOGS, "page.logs.controls", section_key="page.logs.controls"),
    SearchEntry("servers.title", PageName.SERVERS, "page.servers.title"),
    SearchEntry("about.title", PageName.ABOUT, "page.about.title"),
    SearchEntry("about.version", PageName.ABOUT, "page.about.version", section_key="page.about.version"),
    SearchEntry("about.support", PageName.ABOUT, "page.about.support", section_key="page.about.support", tab_key="about", text_prefixes=("page.about.support.",)),
    SearchEntry("about.tab.help", PageName.ABOUT, "page.about.tab.help", section_key="page.about.title", tab_key="help", text_prefixes=("page.about.help.",)),
    SearchEntry("about.support.discussions", PageName.ABOUT, "page.about.support.discussions.title", section_key="page.about.support", tab_key="about"),
    SearchEntry("about.support.telegram", PageName.ABOUT, "page.about.support.telegram.title", section_key="page.about.support", tab_key="about"),
    SearchEntry("about.support.discord", PageName.ABOUT, "page.about.support.discord.title", section_key="page.about.support", tab_key="about"),
    SearchEntry("about.help.docs.forum", PageName.ABOUT, "page.about.help.docs.forum.title", section_key="page.about.tab.help", tab_key="help"),
    SearchEntry("about.help.docs.info", PageName.ABOUT, "page.about.help.docs.info.title", section_key="page.about.tab.help", tab_key="help"),
    SearchEntry("about.help.docs.android", PageName.ABOUT, "page.about.help.docs.android.title", section_key="page.about.tab.help", tab_key="help"),
    SearchEntry("about.help.news.telegram", PageName.ABOUT, "page.about.help.news.telegram.title", section_key="page.about.tab.help", tab_key="help"),
    SearchEntry("about.course.youtube", PageName.ABOUT, "page.about.course.youtube.title", section_key="page.about.title", tab_key="about"),
    SearchEntry("about.course.youtube_playlist", PageName.ABOUT, "page.about.course.youtube_playlist.title", section_key="page.about.title", tab_key="about"),
    SearchEntry("about.help.news.mastodon", PageName.ABOUT, "page.about.help.news.mastodon.title", section_key="page.about.tab.help", tab_key="help"),
    SearchEntry("about.help.news.bastyon", PageName.ABOUT, "page.about.help.news.bastyon.title", section_key="page.about.tab.help", tab_key="help"),
    SearchEntry("support.title", PageName.SUPPORT, "page.support.title"),
    SearchEntry("orch.tab.locked", PageName.ORCHESTRA_SETTINGS, "tab.orchestra.locked", section_key="nav.page.orchestra_settings", tab_key="locked", text_prefixes=("page.orchestra.locked.",)),
    SearchEntry("orch.tab.blocked", PageName.ORCHESTRA_SETTINGS, "tab.orchestra.blocked", section_key="nav.page.orchestra_settings", tab_key="blocked", text_prefixes=("page.orchestra.blocked.",)),
    SearchEntry("orch.tab.whitelist", PageName.ORCHESTRA_SETTINGS, "tab.orchestra.whitelist", section_key="nav.page.orchestra_settings", tab_key="whitelist", text_prefixes=("page.orchestra.whitelist.",)),
    SearchEntry("orch.tab.ratings", PageName.ORCHESTRA_SETTINGS, "tab.orchestra.ratings", section_key="nav.page.orchestra_settings", tab_key="ratings", text_prefixes=("page.orchestra.ratings.",)),
)


_PAGE_SEARCH_EXTRA_PREFIXES: dict[PageName, tuple[str, ...]] = {
    PageName.ZAPRET2_PRESET_SETUP: ("page.winws2_pages.",),
    PageName.ZAPRET1_PRESET_SETUP: ("page.winws1_pages.",),
    PageName.BLOCKCHECK: (
        "page.connection.",
        "page.dns_check.",
        "page.strategy_scan.",
        "page.strategy_sort.",
    ),
}


def _extract_page_prefix(text_key: str | None) -> str | None:
    if not text_key or not text_key.startswith("page."):
        return None

    parts = text_key.split(".")
    if len(parts) < 3:
        return None

    return f"page.{parts[1]}."


def _build_page_search_prefixes() -> dict[PageName, tuple[str, ...]]:
    grouped: dict[PageName, list[str]] = {}

    for entry in SEARCH_ENTRIES:
        page_prefixes = grouped.setdefault(entry.page_name, [])
        for text_key in (entry.text_key, entry.section_key):
            prefix = _extract_page_prefix(text_key)
            if prefix and prefix not in page_prefixes:
                page_prefixes.append(prefix)

    for page_name, extra_prefixes in _PAGE_SEARCH_EXTRA_PREFIXES.items():
        page_prefixes = grouped.setdefault(page_name, [])
        for prefix in extra_prefixes:
            if prefix and prefix not in page_prefixes:
                page_prefixes.append(prefix)

    return {page_name: tuple(prefixes) for page_name, prefixes in grouped.items()}


_PAGE_SEARCH_PREFIXES = _build_page_search_prefixes()
_PAGE_SEARCH_TEXT_CACHE: dict[PageName, tuple[str, ...]] = {}
_CUSTOM_PREFIX_TEXT_CACHE: dict[tuple[str, ...], tuple[str, ...]] = {}


def _get_page_search_texts(page_name: PageName) -> tuple[str, ...]:
    cached = _PAGE_SEARCH_TEXT_CACHE.get(page_name)
    if cached is not None:
        return cached

    prefixes = _PAGE_SEARCH_PREFIXES.get(page_name, ())
    if not prefixes:
        _PAGE_SEARCH_TEXT_CACHE[page_name] = ()
        return ()

    result: list[str] = []
    for text_key in TEXTS:
        if text_key.startswith(prefixes):
            for text in _text_variants(text_key):
                result.append(text)

    unique_result = tuple(dict.fromkeys(result))
    _PAGE_SEARCH_TEXT_CACHE[page_name] = unique_result
    return unique_result


def _normalize_text_prefixes(prefixes: tuple[str, ...]) -> tuple[str, ...]:
    normalized: list[str] = []
    for prefix in prefixes:
        if isinstance(prefix, str) and prefix and prefix not in normalized:
            normalized.append(prefix)
    return tuple(normalized)


def _get_prefixed_search_texts(prefixes: tuple[str, ...]) -> tuple[str, ...]:
    normalized_prefixes = _normalize_text_prefixes(prefixes)
    if not normalized_prefixes:
        return ()

    cached = _CUSTOM_PREFIX_TEXT_CACHE.get(normalized_prefixes)
    if cached is not None:
        return cached

    result: list[str] = []
    for text_key in TEXTS:
        if text_key.startswith(normalized_prefixes):
            for text in _text_variants(text_key):
                result.append(text)

    unique_result = tuple(dict.fromkeys(result))
    _CUSTOM_PREFIX_TEXT_CACHE[normalized_prefixes] = unique_result
    return unique_result


def _is_primary_page_entry(entry: SearchEntry) -> bool:
    return entry.section_key is None and entry.tab_key is None and entry.entry_id.endswith(".title")


_PROFILE_PAGE_BY_METHOD = {
    ZAPRET2_MODE: PageName.ZAPRET2_PRESET_SETUP,
    ZAPRET1_MODE: PageName.ZAPRET1_PRESET_SETUP,
}

_PRESET_PAGE_BY_METHOD = {
    ZAPRET2_MODE: PageName.ZAPRET2_USER_PRESETS,
    ZAPRET1_MODE: PageName.ZAPRET1_USER_PRESETS,
}


def build_profile_search_entries(launch_method: str, profiles: Iterable[object]) -> tuple[SearchEntry, ...]:
    page_name = _PROFILE_PAGE_BY_METHOD.get(normalize_launch_method(launch_method, default=""))
    if page_name is None:
        return ()

    entries: list[SearchEntry] = []
    seen: set[str] = set()
    for index, profile in enumerate(tuple(profiles or ())):
        title = str(getattr(profile, "display_name", "") or getattr(profile, "profile_name", "") or "").strip()
        if not title:
            continue
        key = str(getattr(profile, "key", "") or index).strip()
        dedupe_key = key.casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        keywords = tuple(
            part
            for part in (
                str(getattr(profile, "group_name", "") or "").strip(),
                str(getattr(profile, "group", "") or "").strip(),
                str(getattr(profile, "strategy_name", "") or "").strip(),
                str(getattr(profile, "strategy_id", "") or "").strip(),
                str(getattr(profile, "list_type", "") or "").strip(),
            )
            if part
        )
        entries.append(
            SearchEntry(
                entry_id=f"profile.{normalize_launch_method(launch_method, default='preset')}.{key}",
                page_name=page_name,
                kind="profile",
                title=title,
                location="Профили пресета",
                query_text=title,
                keywords=keywords,
            )
        )
    return tuple(entries)


def build_preset_search_entries(launch_method: str, manifests: Iterable[object]) -> tuple[SearchEntry, ...]:
    page_name = _PRESET_PAGE_BY_METHOD.get(normalize_launch_method(launch_method, default=""))
    if page_name is None:
        return ()

    entries: list[SearchEntry] = []
    seen: set[str] = set()
    for index, manifest in enumerate(tuple(manifests or ())):
        file_name = str(getattr(manifest, "file_name", "") or "").strip()
        title = str(getattr(manifest, "name", "") or "").strip()
        if not title and file_name:
            title = Path(file_name).stem.strip() or file_name
        if not title:
            continue
        key = file_name or str(index)
        dedupe_key = key.casefold()
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)
        keywords = (file_name,) if file_name else ()
        entries.append(
            SearchEntry(
                entry_id=f"preset.{normalize_launch_method(launch_method, default='preset')}.{key}",
                page_name=page_name,
                kind="preset",
                title=title,
                location="Мои пресеты",
                query_text=title,
                keywords=keywords,
            )
        )
    return tuple(entries)


def format_search_result(entry: SearchEntry, language: str | None = None) -> tuple[str, str]:
    title = entry.title or tr(entry.text_key, language=language)
    if entry.location:
        return title, entry.location

    page_label = get_nav_page_label(entry.page_name, language=language)

    section = ""
    if entry.section_key:
        section = tr(entry.section_key, language=language)

    location = page_label if not section else f"{page_label} / {section}"
    return title, location


def _iter_candidate_texts(entry: SearchEntry) -> Iterable[str]:
    for text in (entry.title, entry.location, entry.query_text):
        if isinstance(text, str) and text:
            yield text

    for text in _text_variants(entry.text_key):
        yield text

    nav_key = NAV_PAGE_TEXT_KEYS.get(entry.page_name)
    if nav_key:
        for text in _text_variants(nav_key):
            yield text

    for text in _text_variants(entry.section_key):
        yield text

    for keyword in entry.keywords:
        if isinstance(keyword, str) and keyword:
            yield keyword

    for text in _get_prefixed_search_texts(entry.text_prefixes):
        yield text

    if _is_primary_page_entry(entry):
        for text in _get_page_search_texts(entry.page_name):
            yield text


def build_search_filter_text(entry: SearchEntry, language: str | None = None) -> str:
    texts: list[str] = []
    title, location = format_search_result(entry, language=language)
    for text in (title, location, *_iter_candidate_texts(entry)):
        normalized = str(text or "").strip()
        if normalized and normalized not in texts:
            texts.append(normalized)
    return " ".join(texts)


def find_search_entries(
    query: str,
    language: str | None = None,
    *,
    visible_pages: set[PageName] | None = None,
    max_results: int = 12,
    extra_entries: Iterable[SearchEntry] = (),
) -> tuple[SearchMatch, ...]:
    needle = (query or "").strip().casefold()
    if not needle:
        return ()

    lang = normalize_language(language)
    matches: list[SearchMatch] = []

    for entry in (*SEARCH_ENTRIES, *tuple(extra_entries or ())):
        if visible_pages is not None and entry.page_name not in visible_pages:
            continue

        score = 0

        localized_title = (entry.title or tr(entry.text_key, language=lang)).casefold()
        if needle in localized_title:
            score = max(score, 120 if localized_title.startswith(needle) else 100)

        for title_variant in _text_variants(entry.text_key):
            title_variant_cf = title_variant.casefold()
            if needle in title_variant_cf:
                score = max(score, 115 if title_variant_cf.startswith(needle) else 95)
                break

        localized_section = tr(entry.section_key, language=lang, default="") if entry.section_key else ""
        if localized_section and needle in localized_section.casefold():
            score = max(score, 85)

        for section_variant in _text_variants(entry.section_key):
            if needle in section_variant.casefold():
                score = max(score, 82)
                break

        localized_page = get_nav_page_label(entry.page_name, language=lang).casefold()
        if needle in localized_page:
            score = max(score, 70)

        nav_key = NAV_PAGE_TEXT_KEYS.get(entry.page_name)
        for page_variant in _text_variants(nav_key):
            if needle in page_variant.casefold():
                score = max(score, 68)
                break

        for prefixed_text in _get_prefixed_search_texts(entry.text_prefixes):
            prefixed_cf = prefixed_text.casefold()
            if needle in prefixed_cf:
                score = max(score, 94 if prefixed_cf.startswith(needle) else 78)
                break

        if _is_primary_page_entry(entry):
            for page_text in _get_page_search_texts(entry.page_name):
                page_text_cf = page_text.casefold()
                if needle in page_text_cf:
                    score = max(score, 92 if page_text_cf.startswith(needle) else 76)
                    break

        for candidate in _iter_candidate_texts(entry):
            if needle in candidate.casefold():
                score = max(score, 60)
                break

        if _is_primary_page_entry(entry) and score >= 95:
            score += 1

        if score > 0:
            matches.append(SearchMatch(entry=entry, score=score))

    matches.sort(
        key=lambda item: (
            -item.score,
            _entry_sort_text(item.entry, lang),
            item.entry.entry_id,
        )
    )
    return tuple(matches[: max(1, int(max_results))])


def _entry_sort_text(entry: SearchEntry, language: str) -> str:
    return (entry.title or tr(entry.text_key, language=language)).casefold()
