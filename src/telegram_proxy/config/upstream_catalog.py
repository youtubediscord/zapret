"""Build-time upstream proxy catalog for Telegram proxy UI.

Final contract:
- the selectable proxy list comes only from build/source secrets;
- manual input is a separate UI mode and is not part of the catalog;
- no runtime registry-based proxy list is maintained.
"""

from __future__ import annotations

MANUAL_PRESET_ID = "manual"


def _coerce_port(value) -> int:
    try:
        port = int(value)
    except (TypeError, ValueError):
        return 0
    return port if 0 <= port <= 65535 else 0


def _normalize_name(value: object, fallback: str) -> str:
    text = str(value or "").strip()
    return text or fallback


def _normalize_upstream_preset(
    raw: dict | None,
    *,
    fallback_name: str,
    fallback_id: str,
    source: str,
) -> dict | None:
    if not isinstance(raw, dict):
        return None

    preset_type = str(raw.get("type") or "socks5").strip().lower() or "socks5"
    preset_id = str(raw.get("id") or fallback_id).strip() or fallback_id
    preset = {
        "id": preset_id,
        "name": _normalize_name(raw.get("name"), fallback_name),
        "type": preset_type,
        "source": source,
    }

    if preset_type == "mtproxy":
        link = str(raw.get("link") or "").strip()
        if not link:
            return None
        preset["link"] = link
        return preset

    host = str(raw.get("host") or "").strip()
    port = _coerce_port(raw.get("port"))
    if not host or port <= 0:
        return None

    preset.update(
        {
            "host": host,
            "port": port,
            "username": str(raw.get("username") or "").strip(),
            "password": str(raw.get("password") or ""),
            "tls": bool(raw.get("tls", False)),
            "tls_server_name": str(raw.get("tls_server_name") or "").strip(),
            "tls_verify": bool(raw.get("tls_verify", False)),
        }
    )
    return preset


def _preset_identity_key(preset: dict) -> tuple[str, int, str, str, bool, str, bool] | str | None:
    preset_type = preset.get("type") or "socks5"
    if preset_type == "mtproxy":
        return f"mtproxy:{str(preset.get('link') or '').strip()}"
    if preset_type != "socks5":
        return None
    return (
        str(preset.get("host") or "").strip().lower(),
        _coerce_port(preset.get("port")),
        str(preset.get("username") or "").strip(),
        str(preset.get("password") or ""),
        bool(preset.get("tls", False)),
        str(preset.get("tls_server_name") or "").strip().lower(),
        bool(preset.get("tls_verify", False)),
    )


def _safe_choice_from_preset(preset: dict) -> dict:
    return {
        "id": str(preset.get("id") or "").strip(),
        "name": _normalize_name(preset.get("name"), "Прокси"),
        "type": str(preset.get("type") or "socks5").strip().lower() or "socks5",
    }


def _load_build_upstream_presets() -> list[dict]:
    presets: list[dict] = []

    try:
        from config._build_secrets import PROXY_PRESETS

        if isinstance(PROXY_PRESETS, list):
            for index, raw in enumerate(PROXY_PRESETS, start=1):
                preset = _normalize_upstream_preset(
                    raw,
                    fallback_name=f"Прокси {index}",
                    fallback_id=f"build:{index}",
                    source="build",
                )
                if preset is not None:
                    presets.append(preset)
    except Exception:
        pass

    try:
        from config._build_secrets import MTPROXY_LINK

        if MTPROXY_LINK and not any(p.get("type") == "mtproxy" for p in presets):
            preset = _normalize_upstream_preset(
                {
                    "id": "build:mtproxy",
                    "name": "MTProxy",
                    "type": "mtproxy",
                    "link": MTPROXY_LINK,
                },
                fallback_name="MTProxy",
                fallback_id="build:mtproxy",
                source="build",
            )
            if preset is not None:
                presets.append(preset)
    except Exception:
        pass

    return presets


def _build_choice_list(build_presets: list[dict]) -> list[dict]:
    choices = []
    seen: set[tuple[str, int, str, str, bool, str, bool] | str] = set()

    for preset in build_presets:
        normalized = _normalize_upstream_preset(
            preset,
            fallback_name="Прокси",
            fallback_id=str(preset.get("id") or "build"),
            source=str(preset.get("source") or "build"),
        )
        if normalized is None:
            continue
        key = _preset_identity_key(normalized)
        if key is None or key in seen:
            continue
        seen.add(key)
        choices.append(_safe_choice_from_preset(normalized))

    choices.append(
        {
            "id": MANUAL_PRESET_ID,
            "name": "Ручной ввод",
            "type": "socks5",
        }
    )

    return choices


def _format_preset_label(preset: dict) -> str:
    base_name = str(preset.get("name") or "Прокси").strip() or "Прокси"
    if preset.get("type") == "mtproxy":
        return f"{base_name} (MTProxy)"
    return base_name


class UpstreamCatalog:
    def __init__(self, build_presets: list[dict] | None = None):
        self.choices = _build_choice_list(list(build_presets or []))

    @classmethod
    def load_from_runtime(cls) -> "UpstreamCatalog":
        return cls(build_presets=_load_build_upstream_presets())

    def has_bundled_presets(self) -> bool:
        return any(preset.get("id") != MANUAL_PRESET_ID for preset in self.choices)

    def items(self) -> list[tuple[str, dict]]:
        return [(_format_preset_label(preset), preset) for preset in self.choices]

    def preset_at(self, index: int) -> dict | None:
        if 0 <= index < len(self.choices):
            return self.choices[index]
        return None

    def preset_by_id(self, preset_id: object) -> dict | None:
        target_id = str(preset_id or "").strip()
        if not target_id:
            return None
        for preset in self.choices:
            if str(preset.get("id") or "").strip() == target_id:
                return preset
        return None

    def find_choice_index(
        self,
        *,
        host: str,
        port: int,
        username: str = "",
        password: str = "",
        preset_id: str = "",
    ) -> int:
        target_id = str(preset_id or "").strip()
        if target_id:
            for index, preset in enumerate(self.choices):
                if str(preset.get("id") or "").strip() == target_id:
                    return index

        if str(host or "").strip():
            for index, preset in enumerate(self.choices):
                if str(preset.get("id") or "").strip() == MANUAL_PRESET_ID:
                    return index
        return 0

    def is_manual(self, index: int) -> bool:
        preset = self.preset_at(index)
        return bool(preset and preset.get("id") == MANUAL_PRESET_ID)

    def is_mtproxy(self, index: int) -> bool:
        preset = self.preset_at(index)
        return bool(preset and preset.get("type") == "mtproxy")


class UpstreamPresetResolver:
    def __init__(self, build_presets: list[dict] | None = None):
        self._presets = _build_choice_private_presets(list(build_presets or []))
        self._by_id = {str(preset.get("id") or "").strip(): preset for preset in self._presets}

    @classmethod
    def load_from_runtime(cls) -> "UpstreamPresetResolver":
        return cls(build_presets=_load_build_upstream_presets())

    def socks5_by_id(self, preset_id: object) -> dict | None:
        preset = self._by_id.get(str(preset_id or "").strip())
        if preset is None or preset.get("type") != "socks5":
            return None
        return self._socks5_from_preset(preset)

    def socks5_fallbacks(self, primary_preset_id: object) -> list[dict]:
        primary_id = str(primary_preset_id or "").strip()
        fallbacks: list[dict] = []
        for preset in self._presets:
            if preset.get("type") != "socks5":
                continue
            if primary_id and str(preset.get("id") or "").strip() == primary_id:
                continue
            resolved = self._socks5_from_preset(preset)
            if resolved is not None:
                fallbacks.append(resolved)
        return fallbacks

    def first_socks5(self) -> dict | None:
        for preset in self._presets:
            if preset.get("type") == "socks5":
                return self._socks5_from_preset(preset)
        return None

    def _socks5_from_preset(self, preset: dict) -> dict | None:
        host = str(preset.get("host") or "").strip()
        port = _coerce_port(preset.get("port"))
        if not host or port <= 0:
            return None
        return {
            "id": str(preset.get("id") or "").strip(),
            "name": _normalize_name(preset.get("name"), "Прокси"),
            "host": host,
            "port": port,
            "username": str(preset.get("username") or "").strip(),
            "password": str(preset.get("password") or ""),
            "tls": bool(preset.get("tls", False)),
            "tls_server_name": str(preset.get("tls_server_name") or "").strip(),
            "tls_verify": bool(preset.get("tls_verify", False)),
        }

    def mtproxy_link_by_id(self, preset_id: object) -> str:
        preset = self._by_id.get(str(preset_id or "").strip())
        if preset is None or preset.get("type") != "mtproxy":
            return ""
        return str(preset.get("link") or "").strip()

    def test_target_by_id(self, preset_id: object) -> tuple[str, int, str, str, bool, str, bool] | None:
        preset = self.socks5_by_id(preset_id)
        if preset is None:
            return None
        return (
            str(preset["host"]),
            int(preset["port"]),
            str(preset["username"]),
            str(preset["password"]),
            bool(preset.get("tls", False)),
            str(preset.get("tls_server_name") or ""),
            bool(preset.get("tls_verify", False)),
        )


def _build_choice_private_presets(build_presets: list[dict]) -> list[dict]:
    presets = []
    seen: set[tuple[str, int, str, str, bool, str, bool] | str] = set()
    for preset in build_presets:
        normalized = _normalize_upstream_preset(
            preset,
            fallback_name="Прокси",
            fallback_id=str(preset.get("id") or "build"),
            source=str(preset.get("source") or "build"),
        )
        if normalized is None:
            continue
        key = _preset_identity_key(normalized)
        if key is None or key in seen:
            continue
        seen.add(key)
        presets.append(normalized)
    return presets
