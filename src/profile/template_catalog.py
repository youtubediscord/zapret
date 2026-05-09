from __future__ import annotations

from pathlib import Path

from log.log import log

from .models import EngineName, Profile
from .parser import parse_preset_text


def profile_template_root() -> Path:
    return Path(__file__).resolve().parent / "templates"


def load_profile_templates(engine: EngineName) -> dict[str, Profile]:
    """Читает UI-шаблоны profile.

    Это не runtime storage: шаблоны нужны только для создания нового profile
    внутри выбранного preset. После добавления в preset живёт обычный profile.
    """
    normalized_engine = str(engine or "").strip().lower()
    path = profile_template_root() / "all_profiles.txt"
    templates: dict[str, Profile] = {}
    if not path.exists():
        return templates

    seen_signatures: set[str] = set()
    try:
        preset = parse_preset_text(
            path.read_text(encoding="utf-8", errors="replace"),
            engine=normalized_engine,
            source_name=path.name,
        )
    except Exception as exc:
        log(f"ProfileTemplateCatalog: не удалось прочитать {path.name}: {exc}", "DEBUG")
        return templates

    for profile in preset.profiles:
        signature = profile.match_signature
        if not signature or signature in seen_signatures:
            continue
        if getattr(profile.strategy, "strategy_lines", ()):
            log(f"ProfileTemplateCatalog: {path.name} содержит strategy, шаблон пропущен", "DEBUG")
            continue
        template_id = f"all_profiles:{profile.index}"
        templates[template_id] = profile
        seen_signatures.add(signature)

    return templates
