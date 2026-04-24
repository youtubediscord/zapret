# donater/storage.py

from __future__ import annotations

import base64
import configparser
import contextlib
import hashlib
import json
import os
import platform
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, Optional

from config.config import MAIN_DIRECTORY
from safe_construct import safe_construct


class _CaseConfigParser(configparser.ConfigParser):
    """ConfigParser that preserves option key casing."""

    def optionxform(self, optionstr: str) -> str:  # type: ignore[override]
        return optionstr

_INI_SECTION = "premium"
_INI_LOCK = threading.Lock()


class PremiumStorage:
    """
    Single storage for premium state.

    Windows: <install_dir>\\premium.ini
    """

    @staticmethod
    def path() -> Path:
        base = (MAIN_DIRECTORY or "").strip()
        if not base:
            raise RuntimeError("Не удалось определить корень данных premium")
        return Path(base) / "premium.ini"

    @staticmethod
    def _read(path: Path) -> configparser.ConfigParser:
        try:
            parser = safe_construct(_CaseConfigParser, strict=False)
            if path.exists():
                parser.read(path, encoding="utf-8")
            return parser
        except Exception:
            # Best-effort: keep the app running even if INI parsing breaks.
            # Callers treat missing values as defaults and will regenerate state.
            parser = safe_construct(_CaseConfigParser, strict=False)
            return parser

    @staticmethod
    def _write(path: Path, parser: configparser.ConfigParser) -> bool:
        try:
            path.parent.mkdir(parents=True, exist_ok=True)
            tmp = path.with_suffix(path.suffix + ".tmp")
            with tmp.open("w", encoding="utf-8") as f:
                f.write("# Zapret GUI: premium storage\n")
                parser.write(f)
            tmp.replace(path)
            return True
        except Exception:
            return False

    @staticmethod
    @contextlib.contextmanager
    def _interprocess_lock(path: Path):
        lock_path = path.with_suffix(path.suffix + ".lock")
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        f = None
        try:
            f = lock_path.open("a+", encoding="utf-8")
            if os.name == "nt":
                import msvcrt  # type: ignore

                f.seek(0)
                try:
                    msvcrt.locking(f.fileno(), msvcrt.LK_LOCK, 1)
                except OSError:
                    pass
            else:
                import fcntl  # type: ignore

                try:
                    fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                except OSError:
                    pass
            yield
        finally:
            try:
                if f is not None:
                    if os.name == "nt":
                        import msvcrt  # type: ignore

                        f.seek(0)
                        try:
                            msvcrt.locking(f.fileno(), msvcrt.LK_UNLCK, 1)
                        except OSError:
                            pass
                    else:
                        import fcntl  # type: ignore

                        try:
                            fcntl.flock(f.fileno(), fcntl.LOCK_UN)
                        except OSError:
                            pass
                    f.close()
            except Exception:
                pass

    @staticmethod
    def update(update_fn) -> bool:
        with _INI_LOCK:
            path = PremiumStorage.path()
            with PremiumStorage._interprocess_lock(path):
                parser = PremiumStorage._read(path)
                if not parser.has_section(_INI_SECTION):
                    parser.add_section(_INI_SECTION)
                try:
                    update_fn(parser)
                except Exception:
                    return False
                return PremiumStorage._write(path, parser)

    @staticmethod
    def _machine_info() -> str:
        try:
            return f"{platform.machine()}-{platform.processor()}-{platform.node()}"
        except Exception:
            return "unknown"

    @staticmethod
    def _xor_keystream(seed: bytes, n: int) -> bytes:
        out = bytearray()
        counter = 0
        while len(out) < n:
            block = hashlib.sha256(seed + b"|" + str(counter).encode("ascii")).digest()
            out.extend(block)
            counter += 1
        return bytes(out[:n])

    @staticmethod
    def _obfuscate_activation_key(plain: str, device_id: str) -> str:
        plain_b = (plain or "").encode("utf-8")
        seed = hashlib.sha256(
            ("zapret-premium|xor-v1|" + (device_id or "") + "|" + PremiumStorage._machine_info()).encode("utf-8")
        ).digest()
        ks = PremiumStorage._xor_keystream(seed, len(plain_b))
        obf = bytes([a ^ b for a, b in zip(plain_b, ks)])
        return base64.urlsafe_b64encode(obf).decode("ascii")

    @staticmethod
    def _deobfuscate_activation_key(obf_b64: str, device_id: str) -> Optional[str]:
        try:
            raw = base64.urlsafe_b64decode((obf_b64 or "").encode("ascii"))
            seed = hashlib.sha256(
                ("zapret-premium|xor-v1|" + (device_id or "") + "|" + PremiumStorage._machine_info()).encode("utf-8")
            ).digest()
            ks = PremiumStorage._xor_keystream(seed, len(raw))
            plain_b = bytes([a ^ b for a, b in zip(raw, ks)])
            plain = plain_b.decode("utf-8", errors="strict").strip()
            return plain or None
        except Exception:
            return None

    # --- High-level fields ---

    @staticmethod
    def get_device_id() -> str:
        try:
            with _INI_LOCK:
                path = PremiumStorage.path()
                parser = PremiumStorage._read(path)
                if parser.has_section(_INI_SECTION):
                    device_id = (parser.get(_INI_SECTION, "device_id", fallback="") or "").strip()
                    if device_id:
                        return device_id
        except Exception:
            pass

        device_id = hashlib.md5(PremiumStorage._machine_info().encode()).hexdigest()
        PremiumStorage.update(lambda p: p.set(_INI_SECTION, "device_id", device_id))
        return device_id

    @staticmethod
    def get_device_token() -> Optional[str]:
        try:
            with _INI_LOCK:
                path = PremiumStorage.path()
                parser = PremiumStorage._read(path)
                if not parser.has_section(_INI_SECTION):
                    return None
                v = (parser.get(_INI_SECTION, "device_token", fallback="") or "").strip()
                return v or None
        except Exception:
            return None

    @staticmethod
    def set_device_token(token: str) -> bool:
        token = (token or "").strip()
        if not token:
            return False
        return bool(PremiumStorage.update(lambda p: p.set(_INI_SECTION, "device_token", token)))

    @staticmethod
    def clear_device_token() -> bool:
        return bool(PremiumStorage.update(lambda p: p.remove_option(_INI_SECTION, "device_token")))

    @staticmethod
    def get_last_check() -> Optional[datetime]:
        try:
            with _INI_LOCK:
                path = PremiumStorage.path()
                parser = PremiumStorage._read(path)
                if not parser.has_section(_INI_SECTION):
                    return None
                raw = (parser.get(_INI_SECTION, "last_check", fallback="") or "").strip()
            return datetime.fromisoformat(raw) if raw else None
        except Exception:
            return None

    @staticmethod
    def save_last_check() -> bool:
        ts = datetime.now().isoformat()
        return bool(PremiumStorage.update(lambda p: p.set(_INI_SECTION, "last_check", ts)))

    @staticmethod
    def get_last_network_failure_ts() -> Optional[int]:
        try:
            with _INI_LOCK:
                path = PremiumStorage.path()
                parser = PremiumStorage._read(path)
                if not parser.has_section(_INI_SECTION):
                    return None
                raw = (parser.get(_INI_SECTION, "last_network_failure_ts", fallback="") or "").strip()
            return int(raw) if raw else None
        except Exception:
            return None

    @staticmethod
    def save_last_network_failure_now() -> bool:
        ts = int(time.time())
        return bool(PremiumStorage.update(lambda p: p.set(_INI_SECTION, "last_network_failure_ts", str(ts))))

    @staticmethod
    def clear_last_network_failure() -> bool:
        return bool(PremiumStorage.update(lambda p: p.remove_option(_INI_SECTION, "last_network_failure_ts")))

    @staticmethod
    def get_activation_key() -> Optional[str]:
        try:
            with _INI_LOCK:
                path = PremiumStorage.path()
                parser = PremiumStorage._read(path)
                if not parser.has_section(_INI_SECTION):
                    return None
                device_id = (parser.get(_INI_SECTION, "device_id", fallback="") or "").strip() or PremiumStorage.get_device_id()
                fmt = (parser.get(_INI_SECTION, "activation_key_fmt", fallback="") or "").strip().lower()
                if fmt == "xor-v1":
                    obf = (parser.get(_INI_SECTION, "activation_key_obf", fallback="") or "").strip()
                    if obf:
                        return PremiumStorage._deobfuscate_activation_key(obf, device_id)
                plain = (parser.get(_INI_SECTION, "activation_key", fallback="") or "").strip()
                return plain or None
        except Exception:
            return None

    @staticmethod
    def set_activation_key(key: str) -> bool:
        key = (key or "").strip()
        if not key:
            return False
        device_id = PremiumStorage.get_device_id()

        def _upd(p: configparser.ConfigParser) -> None:
            p.set(_INI_SECTION, "activation_key_fmt", "xor-v1")
            p.set(_INI_SECTION, "activation_key_obf", PremiumStorage._obfuscate_activation_key(key, device_id))

        return bool(PremiumStorage.update(_upd))

    @staticmethod
    def clear_activation_key() -> bool:
        def _upd(p: configparser.ConfigParser) -> None:
            p.remove_option(_INI_SECTION, "activation_key_fmt")
            p.remove_option(_INI_SECTION, "activation_key_obf")
            p.remove_option(_INI_SECTION, "activation_key")

        return bool(PremiumStorage.update(_upd))

    # --- Pairing code (8 chars, TTL ~10 min) ---

    @staticmethod
    def get_pair_code() -> Optional[str]:
        try:
            with _INI_LOCK:
                path = PremiumStorage.path()
                parser = PremiumStorage._read(path)
                if not parser.has_section(_INI_SECTION):
                    return None
                v = (parser.get(_INI_SECTION, "pair_code", fallback="") or "").strip().upper()
                return v or None
        except Exception:
            return None

    @staticmethod
    def get_pair_expires_at() -> Optional[int]:
        try:
            with _INI_LOCK:
                path = PremiumStorage.path()
                parser = PremiumStorage._read(path)
                if not parser.has_section(_INI_SECTION):
                    return None
                raw = (parser.get(_INI_SECTION, "pair_expires_at", fallback="") or "").strip()
            return int(raw) if raw else None
        except Exception:
            return None

    @staticmethod
    def set_pair_code(*, code: str, expires_at: int) -> bool:
        code = (code or "").strip().upper()
        try:
            expires_at_i = int(expires_at)
        except Exception:
            return False
        if not code or expires_at_i <= 0:
            return False

        def _upd(p: configparser.ConfigParser) -> None:
            p.set(_INI_SECTION, "pair_code", code)
            p.set(_INI_SECTION, "pair_expires_at", str(expires_at_i))

        return bool(PremiumStorage.update(_upd))

    @staticmethod
    def clear_pair_code() -> bool:
        def _upd(p: configparser.ConfigParser) -> None:
            p.remove_option(_INI_SECTION, "pair_code")
            p.remove_option(_INI_SECTION, "pair_expires_at")

        return bool(PremiumStorage.update(_upd))

    @staticmethod
    def get_premium_cache() -> Optional[Dict[str, Any]]:
        try:
            with _INI_LOCK:
                path = PremiumStorage.path()
                parser = PremiumStorage._read(path)
                if not parser.has_section(_INI_SECTION):
                    return None
                raw = (parser.get(_INI_SECTION, "premium_cache_json", fallback="") or "").strip()
            if not raw:
                return None
            data = json.loads(raw)
            return data if isinstance(data, dict) else None
        except Exception:
            return None

    @staticmethod
    def set_premium_cache(cache: Dict[str, Any]) -> bool:
        if not isinstance(cache, dict):
            return False
        raw = json.dumps(cache, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
        return bool(PremiumStorage.update(lambda p: p.set(_INI_SECTION, "premium_cache_json", raw)))

    @staticmethod
    def clear_premium_cache() -> bool:
        return bool(PremiumStorage.update(lambda p: p.remove_option(_INI_SECTION, "premium_cache_json")))

    # --- Atomic application helpers ---

    @staticmethod
    def store_after_activation(
        *,
        device_id: str,
        device_token: str,
        activation_key: str,
        signed_payload: Dict[str, Any],
        kid: Optional[str],
        sig: Optional[str],
    ) -> bool:
        device_id = (device_id or "").strip()
        device_token = (device_token or "").strip()
        activation_key = (activation_key or "").strip()
        if not device_id or not device_token or not activation_key or not isinstance(signed_payload, dict):
            return False

        def _upd(p: configparser.ConfigParser) -> None:
            p.set(_INI_SECTION, "device_id", device_id)
            p.set(_INI_SECTION, "device_token", device_token)
            p.set(_INI_SECTION, "last_check", datetime.now().isoformat())
            p.set(_INI_SECTION, "activation_key_fmt", "xor-v1")
            p.set(_INI_SECTION, "activation_key_obf", PremiumStorage._obfuscate_activation_key(activation_key, device_id))
            cache = {"kid": kid, "sig": sig, "signed": signed_payload, "cached_at": int(time.time())}
            p.set(_INI_SECTION, "premium_cache_json", json.dumps(cache, ensure_ascii=False, separators=(",", ":"), sort_keys=True))

        return bool(PremiumStorage.update(_upd))

    @staticmethod
    def store_after_pairing(
        *,
        device_id: str,
        device_token: str,
        signed_payload: Dict[str, Any],
        kid: Optional[str],
        sig: Optional[str],
    ) -> bool:
        device_id = (device_id or "").strip()
        device_token = (device_token or "").strip()
        if not device_id or not device_token or not isinstance(signed_payload, dict):
            return False

        def _upd(p: configparser.ConfigParser) -> None:
            p.set(_INI_SECTION, "device_id", device_id)
            p.set(_INI_SECTION, "device_token", device_token)
            p.set(_INI_SECTION, "last_check", datetime.now().isoformat())
            # Pair code is one-time; clear after success.
            p.remove_option(_INI_SECTION, "pair_code")
            p.remove_option(_INI_SECTION, "pair_expires_at")
            cache = {"kid": kid, "sig": sig, "signed": signed_payload, "cached_at": int(time.time())}
            p.set(_INI_SECTION, "premium_cache_json", json.dumps(cache, ensure_ascii=False, separators=(",", ":"), sort_keys=True))

        return bool(PremiumStorage.update(_upd))

    @staticmethod
    def store_status_active(*, signed_payload: Dict[str, Any], kid: Optional[str], sig: Optional[str]) -> bool:
        if not isinstance(signed_payload, dict):
            return False

        def _upd(p: configparser.ConfigParser) -> None:
            p.set(_INI_SECTION, "last_check", datetime.now().isoformat())
            cache = {"kid": kid, "sig": sig, "signed": signed_payload, "cached_at": int(time.time())}
            p.set(_INI_SECTION, "premium_cache_json", json.dumps(cache, ensure_ascii=False, separators=(",", ":"), sort_keys=True))

        return bool(PremiumStorage.update(_upd))

    @staticmethod
    def apply_status_inactive(*, message: str) -> bool:
        # Keep device_token; just clear premium cache and update last_check.
        def _upd(p: configparser.ConfigParser) -> None:
            p.set(_INI_SECTION, "last_check", datetime.now().isoformat())
            p.remove_option(_INI_SECTION, "premium_cache_json")

        return bool(PremiumStorage.update(_upd))
