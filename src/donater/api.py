# donater/api.py

from __future__ import annotations

import secrets
from typing import Any, Dict, Optional, Tuple

import requests


class PremiumApiClient:
    def __init__(self, *, base_url: str, timeout: int = 10):
        self.base_url = (base_url or "").rstrip("/")
        self.timeout = int(timeout)
        # Bypass system/env proxy settings to avoid interference from DPI tools (winws/winws2)
        # that may configure system proxy or set HTTP_PROXY/HTTPS_PROXY env vars.
        self._session = requests.Session()
        self._session.trust_env = False

    def _url(self, endpoint: str) -> str:
        endpoint = (endpoint or "").lstrip("/")
        return f"{self.base_url}/{endpoint}"

    @staticmethod
    def _truncate_text(s: str, limit: int = 400) -> str:
        s = (s or "").strip()
        if not s:
            return ""
        if len(s) <= limit:
            return s
        return s[: limit - 3] + "..."

    @staticmethod
    def _response_to_dict(r: requests.Response, *, nonce: str) -> Dict[str, Any]:
        """Best-effort convert HTTP response into a dict with debug metadata."""
        data: Dict[str, Any]
        try:
            parsed = r.json() if r.content else None
        except Exception:
            parsed = None

        if isinstance(parsed, dict):
            data = parsed
        else:
            data = {
                "success": False,
                "error": "Некорректный ответ сервера",
            }

        # Attach metadata for debugging (client-side only).
        try:
            data.setdefault("_nonce", nonce)
            data.setdefault("_http_status", int(getattr(r, "status_code", 0) or 0))
            if not data.get("_http_text"):
                data["_http_text"] = PremiumApiClient._truncate_text(getattr(r, "text", "") or "")
        except Exception:
            pass

        return data

    @staticmethod
    def _exception_to_dict(e: Exception, *, nonce: str) -> Dict[str, Any]:
        # Keep message short and user-facing.
        name = e.__class__.__name__
        msg = (str(e) or "").strip()
        text = (name + (": " + msg if msg else "")).strip()
        return {
            "success": False,
            "error": "Ошибка сети",
            "detail": PremiumApiClient._truncate_text(text, 400),
            "_nonce": nonce,
            "_http_status": 0,
        }

    def get_status(self) -> Optional[Dict[str, Any]]:
        nonce = ""  # no nonce for GET
        try:
            r = self._session.get(self._url("status"), timeout=self.timeout)
            # Always return dict with HTTP metadata when possible.
            return self._response_to_dict(r, nonce=nonce)
        except Exception as e:
            return self._exception_to_dict(e, nonce=nonce)

    def post_activate(self, *, key: str, device_id: str) -> Tuple[Optional[Dict[str, Any]], str]:
        # Legacy endpoint (removed in new pairing architecture).
        nonce = secrets.token_urlsafe(16)
        return (None, nonce)

    def post_pair_start(self, *, device_id: str, device_name: str | None = None) -> Tuple[Optional[Dict[str, Any]], str]:
        nonce = secrets.token_urlsafe(16)
        try:
            try:
                from log.log import log


                log(
                    f"Premium pair_start request: base_url={self.base_url!r}, device_id={device_id[:12]}..., nonce={nonce[:8]}...",
                    "DEBUG",
                )
            except Exception:
                pass

            r = self._session.post(
                self._url("pair_start"),
                json={"device_id": device_id, "device_name": device_name, "nonce": nonce},
                timeout=self.timeout,
            )
            data = self._response_to_dict(r, nonce=nonce)
            try:
                from log.log import log


                log(
                    "Premium pair_start response: "
                    f"http={data.get('_http_status')}, "
                    f"success={data.get('success')}, "
                    f"type={data.get('type')}, "
                    f"error={data.get('error')!r}, "
                    f"message={data.get('message')!r}",
                    "DEBUG",
                )
            except Exception:
                pass
            return (data, nonce)
        except Exception as e:
            data = self._exception_to_dict(e, nonce=nonce)
            try:
                from log.log import log


                log(
                    f"Premium pair_start exception: base_url={self.base_url!r}, error={data.get('detail')!r}",
                    "WARNING",
                )
            except Exception:
                pass
            return (data, nonce)

    def post_pair_finish(self, *, device_id: str, pair_code: str) -> Tuple[Optional[Dict[str, Any]], str]:
        nonce = secrets.token_urlsafe(16)
        try:
            r = self._session.post(
                self._url("pair_finish"),
                json={"device_id": device_id, "pair_code": pair_code, "nonce": nonce},
                timeout=self.timeout,
            )
            return (self._response_to_dict(r, nonce=nonce), nonce)
        except Exception as e:
            return (self._exception_to_dict(e, nonce=nonce), nonce)

    def post_check(self, *, device_id: str, device_token: str) -> Tuple[Optional[Dict[str, Any]], str]:
        nonce = secrets.token_urlsafe(16)
        try:
            r = self._session.post(
                self._url("check_device"),
                json={"device_id": device_id, "device_token": device_token, "nonce": nonce},
                timeout=self.timeout,
            )
            return (self._response_to_dict(r, nonce=nonce), nonce)
        except Exception as e:
            return (self._exception_to_dict(e, nonce=nonce), nonce)
