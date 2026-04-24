# donater/service.py

from __future__ import annotations

import threading
import time
from typing import Any, Dict, Optional, Tuple

from .api import PremiumApiClient
from .crypto import verify_signed_response
from .storage import PremiumStorage
from .types import ActivationStatus

try:
    from config._build_secrets import PREMIUM_API_BASE_URL as API_BASE_URL
except ImportError:
    API_BASE_URL = ""
REQUEST_TIMEOUT = 5
AUTO_NETWORK_RETRY_COOLDOWN_SEC = 30
PAIR_CODE_TTL_MINUTES = 10


def _safe_int(value: Any) -> int:
    try:
        return int(str(value))
    except Exception:
        return 0


def _collect_api_message_bits(raw_any: Any) -> list[str]:
    if not isinstance(raw_any, dict):
        return []

    bits: list[str] = []
    for key in ("error", "message", "detail", "status", "_http_text"):
        value = str(raw_any.get(key) or "").strip()
        if value and value not in bits:
            bits.append(value)
    return bits


def _contains_error_token(text: str, *tokens: str) -> bool:
    haystack = str(text or "").casefold()
    return any(str(token or "").casefold() in haystack for token in tokens)


def _format_pair_finish_error(raw_any: Any) -> tuple[Optional[str], bool]:
    """
    Convert backend `pair_finish` errors into short user-facing hints.

    Returns:
        (message, clear_local_pair_code)
    """
    if not isinstance(raw_any, dict):
        return None, False

    http_i = _safe_int(raw_any.get("_http_status"))
    joined = " | ".join(_collect_api_message_bits(raw_any))
    if not joined:
        return None, False

    if _contains_error_token(
        joined,
        "pair_code_not_found",
        "pair code not found",
        "code not found",
        "код не найден",
        "истёк",
        "истек",
        "expired",
    ):
        return (
            "Код привязки не найден на сервере или уже перестал действовать. "
            f"Создайте новый код и сразу отправьте его боту. Код живёт около {PAIR_CODE_TTL_MINUTES} минут. "
            "Если это повторяется сразу после создания, обычно запущена старая версия приложения, "
            "в приложении остался прежний код или бот и приложение подключены к разным серверам Premium.",
            True,
        )

    if _contains_error_token(
        joined,
        "pair_code_used",
        "already used",
        "already paired",
        "код уже использован",
        "код уже привязан",
    ):
        return (
            "Этот код уже был использован. Создайте новый код в приложении и отправьте именно его.",
            True,
        )

    if _contains_error_token(
        joined,
        "ошибка сети",
        "timeout",
        "timed out",
        "connection error",
        "connection refused",
        "connection aborted",
        "temporarily unavailable",
    ):
        return (
            "Не удалось проверить код из-за сети. Нажмите «Проверить соединение» и попробуйте ещё раз.",
            False,
        )

    if http_i >= 400:
        return (f"Ошибка привязки (HTTP {http_i}): {joined}", False)
    if raw_any.get("success") is False:
        return (f"Ошибка привязки: {joined}", False)
    return None, False


class PremiumService:
    """
    Minimal "actor" service:
    - One lock for all premium operations (activate/check/clear).
    - Single storage (premium.ini).
    """

    def __init__(self, *, api_base_url: str = API_BASE_URL, timeout: int = REQUEST_TIMEOUT):
        self._lock = threading.Lock()
        self._api = PremiumApiClient(base_url=api_base_url, timeout=timeout)

    @property
    def device_id(self) -> str:
        return PremiumStorage.get_device_id()

    def test_connection(self) -> Tuple[bool, str]:
        with self._lock:
            result = self._api.get_status()
            if isinstance(result, dict) and result.get("success"):
                version = result.get("version", "unknown")
                return True, f"API сервер доступен (v{version})"

            # Best-effort diagnostics for non-200 / non-success responses.
            if isinstance(result, dict):
                http = result.get("_http_status")
                err = (
                    result.get("error")
                    or result.get("message")
                    or result.get("detail")
                    or result.get("status")
                    or ""
                )
                text = (result.get("_http_text") or "").strip()
                bits = []
                if http:
                    bits.append(f"HTTP {http}")
                if err:
                    bits.append(str(err))
                elif text:
                    bits.append(text)
                return False, "API недоступен" + (": " + " | ".join(bits) if bits else "")

            return False, "API недоступен"

    def pair_start(self, *, device_name: Optional[str] = None) -> Tuple[bool, str, Optional[str]]:
        """
        Create 8-char pairing code (TTL ~10 min). User sends this code to Telegram bot.
        """
        with self._lock:
            device_id = PremiumStorage.get_device_id()
            try:
                from log.log import log


                log(
                    f"PremiumService.pair_start begin: api_base={self._api.base_url!r}, device_id={device_id[:12]}...",
                    "DEBUG",
                )
            except Exception:
                pass

            raw, nonce = self._api.post_pair_start(device_id=device_id, device_name=device_name)
            if not raw:
                try:
                    from log.log import log


                    log("PremiumService.pair_start: raw response is empty", "WARNING")
                except Exception:
                    pass
                return False, "Сервер недоступен", None

            signed = verify_signed_response(raw, expected_device_id=device_id, expected_nonce=nonce)
            if not signed or signed.get("type") != "zapret_pair_start":
                try:
                    from log.log import log


                    log(
                        "PremiumService.pair_start invalid signed response: "
                        f"http={raw.get('_http_status') if isinstance(raw, dict) else None}, "
                        f"type={raw.get('type') if isinstance(raw, dict) else None}, "
                        f"error={raw.get('error') if isinstance(raw, dict) else None}, "
                        f"message={raw.get('message') if isinstance(raw, dict) else None}",
                        "WARNING",
                    )
                except Exception:
                    pass
                if isinstance(raw, dict):
                    http = raw.get("_http_status")
                    err = (raw.get("error") or raw.get("message") or raw.get("detail") or raw.get("status") or "").strip()
                    text = (raw.get("_http_text") or "").strip()
                    msg = err or text or "Ошибка создания кода"
                    if http:
                        msg = f"HTTP {http}: {msg}"
                    return False, str(msg), None

                return False, "Ошибка создания кода", None

            code = str(signed.get("pair_code") or "").strip().upper()
            expires_at = signed.get("pair_expires_at")
            try:
                expires_at_i = int(str(expires_at))
            except Exception:
                expires_at_i = 0

            if not code or expires_at_i <= 0:
                try:
                    from log.log import log


                    log(
                        f"PremiumService.pair_start bad payload: code={code!r}, expires_at={expires_at!r}",
                        "WARNING",
                    )
                except Exception:
                    pass
                return False, "Сервер вернул некорректный код", None

            stored = PremiumStorage.set_pair_code(code=code, expires_at=expires_at_i)
            try:
                from log.log import log


                log(
                    f"PremiumService.pair_start success: code={code}, expires_at={expires_at_i}, stored={stored}",
                    "INFO",
                )
            except Exception:
                pass
            return True, str(signed.get("message") or f"Код создан на {PAIR_CODE_TTL_MINUTES} минут"), code

    def clear_activation(self) -> bool:
        with self._lock:
            PremiumStorage.clear_device_token()
            PremiumStorage.clear_premium_cache()
            PremiumStorage.clear_pair_code()
            PremiumStorage.clear_activation_key()
            PremiumStorage.save_last_check()
            return True

    def check_status(self, *, allow_network: bool = True, automatic: bool = False) -> ActivationStatus:
        with self._lock:
            device_id = PremiumStorage.get_device_id()
            device_token = PremiumStorage.get_device_token() or ""
            network_cooldown_active = False

            def _apply_network_health(raw_any: Any) -> None:
                if not isinstance(raw_any, dict):
                    return

                http = raw_any.get("_http_status")
                http_i = 0
                try:
                    http_i = int(str(http))
                except Exception:
                    http_i = 0

                if http_i > 0:
                    PremiumStorage.clear_last_network_failure()
                    return

                if str(raw_any.get("error") or "").strip() == "Ошибка сети":
                    PremiumStorage.save_last_network_failure_now()

            if allow_network and automatic:
                last_failure_ts = PremiumStorage.get_last_network_failure_ts() or 0
                now_ts = int(time.time())
                if last_failure_ts > 0 and (now_ts - last_failure_ts) < AUTO_NETWORK_RETRY_COOLDOWN_SEC:
                    allow_network = False
                    network_cooldown_active = True
                    try:
                        from log.log import log


                        remaining = AUTO_NETWORK_RETRY_COOLDOWN_SEC - max(0, now_ts - last_failure_ts)
                        log(
                            f"Premium auto-check skipped: recent network failure cooldown ({remaining}s left)",
                            "DEBUG",
                        )
                    except Exception:
                        pass

            # If we have a pending pair code (user started pairing), try to finish pairing first.
            # Do it even when we already have a token: token may be stale/invalid on server.
            code = PremiumStorage.get_pair_code()
            exp = PremiumStorage.get_pair_expires_at() or 0
            has_pending_code = bool(code and int(exp) >= int(time.time()))
            pair_error_message: Optional[str] = None
            if allow_network and has_pending_code:
                raw2, nonce2 = self._api.post_pair_finish(device_id=device_id, pair_code=str(code))
                if raw2:
                    _apply_network_health(raw2)
                    pair_error_message, should_clear_pair_code = _format_pair_finish_error(raw2)
                    if should_clear_pair_code:
                        PremiumStorage.clear_pair_code()
                        code = None
                        exp = 0
                        has_pending_code = False
                    signed2 = verify_signed_response(raw2, expected_device_id=device_id, expected_nonce=nonce2)
                    if signed2 and signed2.get("type") == "zapret_premium_activation":
                        token = str(signed2.get("device_token") or "").strip()
                        if token:
                            # Store token even if subscription is currently inactive:
                            # it will become active automatically after renewal (bot sync).
                            PremiumStorage.store_after_pairing(
                                device_id=device_id,
                                device_token=token,
                                signed_payload=signed2,
                                kid=raw2.get("kid") if isinstance(raw2, dict) else None,
                                sig=raw2.get("sig") if isinstance(raw2, dict) else None,
                            )
                            device_token = token
                    elif pair_error_message is None and isinstance(raw2, dict):
                        # Give a useful hint when backend replies but does not return signed activation yet.
                        hint = (
                            raw2.get("error")
                            or raw2.get("message")
                            or raw2.get("detail")
                            or raw2.get("status")
                            or ""
                        )
                        hint_s = str(hint or "").strip()
                        if hint_s:
                            pair_error_message = f"Привязка: {hint_s}"

            # If token is still missing, do not call check_device (server expects a token).
            # We will still allow an offline cache path below.
            if not device_token:
                if pair_error_message:
                    try:
                        from log.log import log


                        log(f"Premium pairing not complete: {pair_error_message}", "INFO")
                    except Exception:
                        pass

                # Offline cache path
                cache = PremiumStorage.get_premium_cache()
                if isinstance(cache, dict):
                    cached_resp = {"kid": cache.get("kid"), "sig": cache.get("sig"), "signed": cache.get("signed")}
                    cached_signed = verify_signed_response(cached_resp, expected_device_id=device_id, expected_nonce=None)
                    if cached_signed and cached_signed.get("activated") is True:
                        valid_until = cached_signed.get("valid_until")
                        expires_at = cached_signed.get("expires_at")
                        try:
                            now_ts = int(time.time())
                            valid_until_i = 0
                            try:
                                valid_until_i = int(str(valid_until))
                            except Exception:
                                valid_until_i = 0

                            if valid_until_i >= now_ts:
                                # Do not allow offline premium past subscription expiry.
                                if expires_at:
                                    from datetime import datetime

                                    dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
                                    if dt.tzinfo is not None:
                                        dt = dt.replace(tzinfo=None)
                                    if dt <= datetime.now():
                                        raise ValueError("expired")
                                return ActivationStatus(
                                    is_activated=True,
                                    days_remaining=cached_signed.get("days_remaining"),
                                    expires_at=cached_signed.get("expires_at"),
                                    status_message="Активировано (offline)",
                                    is_linked=True,
                                    subscription_level=str(cached_signed.get("subscription_level") or "zapretik"),
                                )
                        except Exception:
                            pass

                msg = pair_error_message
                if not msg:
                    if network_cooldown_active:
                        msg = "Недавняя ошибка сети, используем кэш"
                    else:
                        msg = "Ожидание привязки" if has_pending_code else "Устройство не привязано"

                return ActivationStatus(
                    is_activated=False,
                    days_remaining=None,
                    expires_at=None,
                    status_message=msg,
                    is_linked=False,
                    subscription_level="–",
                )

            api_error_message: Optional[str] = None
            if allow_network:
                raw, nonce = self._api.post_check(device_id=device_id, device_token=device_token)

                if isinstance(raw, dict):
                    _apply_network_health(raw)
                    # If server replied with an error (e.g. HTTP 400), surface it to UI/logs.
                    http = raw.get("_http_status")
                    http_i = 0
                    try:
                        http_i = int(str(http))
                    except Exception:
                        http_i = 0

                    if http_i >= 400:
                        err = (
                            raw.get("error")
                            or raw.get("message")
                            or raw.get("detail")
                            or raw.get("status")
                            or ""
                        )
                        text = (raw.get("_http_text") or "").strip()
                        msg = str(err or text or "Ошибка запроса")
                        api_error_message = f"API ошибка (HTTP {http_i}): {msg}"

                    # Some backends may return JSON errors with HTTP 200.
                    if api_error_message is None and raw.get("success") is False:
                        err2 = (
                            raw.get("error")
                            or raw.get("message")
                            or raw.get("detail")
                            or raw.get("status")
                            or ""
                        )
                        text2 = (raw.get("_http_text") or "").strip()
                        msg2 = str(err2 or text2 or "Ошибка запроса")
                        api_error_message = f"API ошибка: {msg2}"

                    signed = verify_signed_response(raw, expected_device_id=device_id, expected_nonce=nonce)
                    if signed and signed.get("type") == "zapret_premium_status":
                        activated = bool(signed.get("activated"))

                        # Best-effort "linked" signal for UI.
                        is_linked: Optional[bool] = None
                        for k in ("found", "linked", "is_linked"):
                            v = signed.get(k)
                            if isinstance(v, bool):
                                is_linked = v
                                break
                        if is_linked is None:
                            msg_l = str(signed.get("message") or "").strip().lower()
                            if "не привяз" in msg_l or "not linked" in msg_l or "not paired" in msg_l:
                                is_linked = False

                        if activated:
                            PremiumStorage.store_status_active(
                                signed_payload=signed,
                                kid=raw.get("kid") if isinstance(raw, dict) else None,
                                sig=raw.get("sig") if isinstance(raw, dict) else None,
                            )
                        else:
                            PremiumStorage.apply_status_inactive(message=str(signed.get("message") or ""))
                        return ActivationStatus(
                            is_activated=activated,
                            days_remaining=signed.get("days_remaining"),
                            expires_at=signed.get("expires_at"),
                            status_message=str(signed.get("message") or ("Активировано" if activated else "Не активировано")),
                            is_linked=is_linked,
                            subscription_level=str(signed.get("subscription_level") or ("zapretik" if activated else "–")),
                        )

                    # If response exists but signature didn't validate, keep a readable hint.
                    if api_error_message is None and raw:
                        http2 = raw.get("_http_status")
                        api_error_message = "Некорректный ответ сервера"
                        if http2:
                            api_error_message += f" (HTTP {http2})"
            elif network_cooldown_active:
                api_error_message = "Недавняя ошибка сети, используем кэш"

            if api_error_message:
                try:
                    from log.log import log


                    log(f"Premium API check failed: {api_error_message}", "WARNING")
                except Exception:
                    pass

            # Offline cache path
            cache = PremiumStorage.get_premium_cache()
            if isinstance(cache, dict):
                cached_resp = {"kid": cache.get("kid"), "sig": cache.get("sig"), "signed": cache.get("signed")}
                cached_signed = verify_signed_response(cached_resp, expected_device_id=device_id, expected_nonce=None)
                if cached_signed and cached_signed.get("activated") is True:
                    valid_until = cached_signed.get("valid_until")
                    expires_at = cached_signed.get("expires_at")
                    try:
                        now_ts = int(time.time())
                        valid_until_i = 0
                        try:
                            valid_until_i = int(str(valid_until))
                        except Exception:
                            valid_until_i = 0

                        if valid_until_i >= now_ts:
                            # Do not allow offline premium past subscription expiry.
                            if expires_at:
                                from datetime import datetime

                                dt = datetime.fromisoformat(str(expires_at).replace("Z", "+00:00"))
                                if dt.tzinfo is not None:
                                    dt = dt.replace(tzinfo=None)
                                if dt <= datetime.now():
                                    raise ValueError("expired")
                            return ActivationStatus(
                                is_activated=True,
                                days_remaining=cached_signed.get("days_remaining"),
                                expires_at=cached_signed.get("expires_at"),
                                status_message="Активировано (offline)",
                                is_linked=True,
                                subscription_level=str(cached_signed.get("subscription_level") or "zapretik"),
                            )
                    except Exception:
                        pass

            return ActivationStatus(
                is_activated=False,
                days_remaining=None,
                expires_at=None,
                status_message=api_error_message or "Не активировано",
                is_linked=None,
                subscription_level="–",
            )

    # Back-compat helpers used around the app:
    def check_device_activation(self, *, use_cache: bool = False, automatic: bool = False) -> Dict[str, Any]:
        st = self.check_status(allow_network=not use_cache, automatic=automatic)
        found = st.is_linked if st.is_linked is not None else (PremiumStorage.get_device_token() is not None)
        return {
            "found": found,
            "activated": st.is_activated,
            "is_premium": st.is_activated,
            "days_remaining": st.days_remaining,
            "status": st.status_message,
            "expires_at": st.expires_at,
            "level": "Premium" if st.subscription_level != "–" else "–",
            "subscription_level": st.subscription_level,
        }

    def get_full_subscription_info(self, *, use_cache: bool = False, automatic: bool = False) -> Dict[str, Any]:
        info = self.check_device_activation(use_cache=use_cache, automatic=automatic)
        is_premium = bool(info.get("activated"))
        status_msg = info.get("status") or ("Premium активен" if is_premium else "Не активировано")
        return {
            "is_premium": is_premium,
            "status_msg": status_msg,
            "days_remaining": info["days_remaining"] if is_premium else None,
            "subscription_level": info["subscription_level"] if is_premium else "–",
        }


_SERVICE: Optional[PremiumService] = None


def get_premium_service() -> PremiumService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = PremiumService()
    return _SERVICE
