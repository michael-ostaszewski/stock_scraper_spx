from __future__ import annotations

import base64
import datetime as dt
import hmac
import hashlib
import json
import secrets
import time
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests
import streamlit as st
try:
    import extra_streamlit_components as stx
except Exception:  # pragma: no cover - optional dependency in local/dev env
    stx = None


AUTH_SESSION_KEY = "supabase_auth_session"
AUTH_FLASH_ERROR_KEY = "supabase_auth_flash_error"
AUTH_PERSIST_COOKIE_NAME = "supabase_auth_persist_v1"
AUTH_REMEMBER_DAYS_DEFAULT = 7
AUTH_LAST_OAUTH_CODE_KEY = "supabase_auth_last_oauth_code"
AUTH_DEGRADED_KEY = "supabase_auth_degraded_info"
AUTH_TRANSIENT_EVENTS_KEY = "supabase_auth_transient_events"
AUTH_DIAG_EVENTS_KEY = "supabase_auth_diag_events"
AUTH_OAUTH_FLOW_KEY = "supabase_auth_oauth_flow"
AUTH_OAUTH_FLOW_COOKIE_NAME = "supabase_auth_oauth_flow_v1"
AUTH_OAUTH_FLOW_TTL_SECONDS = 10 * 60
AUTH_GOOGLE_RETRY_AFTER_SECONDS = 20


class AuthError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        request_id: str | None = None,
        status_code: int | None = None,
        transient: bool = False,
        error_kind: str | None = None,
    ):
        super().__init__(message)
        self.request_id = request_id
        self.status_code = status_code
        self.transient = transient
        self.error_kind = error_kind


def _safe_rerun():
    try:
        st.rerun()
    except Exception:
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()


def _utc_now_iso() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _auth_diag_log(event: str, **fields: Any):
    payload = {"event": event, "ts_utc": _utc_now_iso()}
    payload.update(fields)
    diag = st.session_state.get(AUTH_DIAG_EVENTS_KEY, [])
    if not isinstance(diag, list):
        diag = []
    diag.append(payload)
    st.session_state[AUTH_DIAG_EVENTS_KEY] = diag[-50:]
    try:
        print(f"[auth_diag] {json.dumps(payload, sort_keys=True, ensure_ascii=True)}")
    except Exception:
        pass


def _register_transient_auth_issue(
    reason: str,
    request_id: str | None = None,
    *,
    issue_type: str = "transient",
):
    now_ts = time.time()
    events = st.session_state.get(AUTH_TRANSIENT_EVENTS_KEY, [])
    if not isinstance(events, list):
        events = []
    events = [float(ts) for ts in events if isinstance(ts, (int, float)) and now_ts - float(ts) <= 600.0]
    events.append(now_ts)
    st.session_state[AUTH_TRANSIENT_EVENTS_KEY] = events
    st.session_state[AUTH_DEGRADED_KEY] = {
        "ts_utc": _utc_now_iso(),
        "epoch": now_ts,
        "reason": str(reason),
        "request_id": str(request_id or ""),
        "count_10m": len(events),
        "issue_type": str(issue_type or "transient"),
    }


def _clear_auth_degraded_state():
    st.session_state.pop(AUTH_DEGRADED_KEY, None)


def _append_request_id(message: str, request_id: str | None) -> str:
    rid = str(request_id or "").strip()
    if not rid:
        return message
    return f"{message} (request id: {rid})"


def _grant_type_from_params(params: dict[str, Any] | None) -> str:
    if not isinstance(params, dict):
        return ""
    return str(params.get("grant_type") or "").strip().lower()


def _is_single_use_or_rotating_grant(params: dict[str, Any] | None) -> bool:
    return _grant_type_from_params(params) in {"pkce", "refresh_token"}


def _is_transient_auth_message(message: str) -> bool:
    lowered = str(message or "").lower()
    transient_markers = [
        "upstream connect error",
        "upstream request timeout",
        "remote connection failure",
        "transport failure reason",
        "delayed connect error",
        "connection reset",
        "context deadline exceeded",
        "temporary network error",
        "timeout",
        "503",
        "504",
    ]
    return any(marker in lowered for marker in transient_markers)


def _is_invalid_token_message(message: str) -> bool:
    lowered = str(message or "").lower()
    invalid_markers = [
        "invalid_grant",
        "invalid grant",
        "refresh token not found",
        "refresh token already used",
        "invalid refresh token",
        "token has expired",
        "expired token",
        "revoked",
        "code expired",
        "already used",
        "invalid flow state",
    ]
    return any(marker in lowered for marker in invalid_markers)


def _auth_error_is_transient(exc: AuthError) -> bool:
    return bool(getattr(exc, "transient", False)) or _is_transient_auth_message(str(exc))


def _auth_error_is_invalid_token(exc: AuthError) -> bool:
    return _is_invalid_token_message(str(exc))


def _auth_config() -> dict[str, str]:
    cfg = st.secrets.get("supabase_auth", {})
    base_url = str(cfg.get("url") or cfg.get("project_url") or "").rstrip("/")
    publishable_key = str(cfg.get("publishable_key") or cfg.get("anon_key") or "").strip()

    if not base_url or not publishable_key:
        raise AuthError(
            "Missing Supabase Auth config. Add st.secrets['supabase_auth'] with 'url' and 'publishable_key'."
        )

    return {
        "base_url": base_url,
        "publishable_key": publishable_key,
    }


def _normalize_public_url(raw_url: str) -> str:
    candidate = str(raw_url or "").strip().rstrip("/")
    if not candidate:
        return ""

    parts = urlsplit(candidate)
    if not parts.scheme or not parts.netloc:
        return ""

    path = parts.path or "/"
    return urlunsplit((parts.scheme, parts.netloc, path, "", ""))


def _is_local_netloc(netloc: str) -> bool:
    host = str(netloc or "").strip().lower()
    return host.startswith("localhost") or host.startswith("127.0.0.1")


def _oauth_app_url() -> str:
    cfg = st.secrets.get("supabase_auth", {})
    local_app_url = _normalize_public_url(str(cfg.get("local_app_url") or ""))
    app_url = _normalize_public_url(str(cfg.get("app_url") or ""))

    try:
        current_url = str(getattr(st.context, "url", "") or "").strip()
    except Exception:
        current_url = ""

    normalized_current_url = _normalize_public_url(current_url)
    if normalized_current_url:
        current_netloc = urlsplit(normalized_current_url).netloc
        if _is_local_netloc(current_netloc) and local_app_url:
            return local_app_url

    try:
        host = str(st.context.headers.get("host") or "").strip()
    except Exception:
        host = ""

    if _is_local_netloc(host) and local_app_url:
        return local_app_url

    if app_url:
        return app_url

    if normalized_current_url:
        return normalized_current_url

    if host:
        scheme = "http" if host.startswith(("localhost", "127.0.0.1")) else "https"
        normalized_host_url = _normalize_public_url(f"{scheme}://{host}")
        if normalized_host_url:
            return normalized_host_url

    if local_app_url:
        return local_app_url

    raise AuthError(
        "Missing Supabase OAuth redirect config. Add st.secrets['supabase_auth']['app_url'] "
        "or set st.secrets['supabase_auth']['local_app_url'] for local development."
    )


def _auth_request(
    method: str,
    path: str,
    *,
    params: dict[str, Any] | None = None,
    payload: dict[str, Any] | None = None,
    access_token: str | None = None,
) -> dict[str, Any]:
    cfg = _auth_config()
    headers = {"apikey": cfg["publishable_key"]}
    if payload is not None:
        headers["Content-Type"] = "application/json"
    if access_token:
        headers["Authorization"] = f"Bearer {access_token}"

    def _extract_error_details(resp: requests.Response) -> tuple[str, str | None]:
        message = "Supabase Auth request failed."
        try:
            body = resp.json()
            message = (
                body.get("msg")
                or body.get("message")
                or body.get("error_description")
                or body.get("error")
                or message
            )
        except ValueError:
            if resp.text.strip():
                message = resp.text.strip()
        request_id = (
            str(resp.headers.get("sb-request-id") or "").strip()
            or str(resp.headers.get("x-request-id") or "").strip()
            or None
        )
        return str(message), request_id

    def _is_transient_http_error(status_code: int, message_text: str) -> bool:
        if status_code in {502, 503, 504, 521, 522, 523, 524}:
            return True
        return _is_transient_auth_message(message_text)

    grant_type = _grant_type_from_params(params)
    retry_safe = not _is_single_use_or_rotating_grant(params)
    max_attempts = 3 if retry_safe else 1
    backoff_seconds = [0.4, 1.0]
    last_message = "Supabase Auth request failed."
    last_request_id: str | None = None

    for attempt in range(max_attempts):
        try:
            response = requests.request(
                method=method,
                url=f"{cfg['base_url']}/auth/v1/{path.lstrip('/')}",
                params=params,
                json=payload,
                headers=headers,
                timeout=15,
            )
        except requests.RequestException as exc:
            last_message = f"Temporary network error while contacting Supabase Auth: {exc}"
            _auth_diag_log(
                "auth_request_network_error",
                method=method,
                path=path,
                grant_type=grant_type,
                retry_safe=retry_safe,
                attempt=attempt + 1,
                max_attempts=max_attempts,
                error=str(exc),
            )
            if retry_safe and attempt < max_attempts - 1:
                time.sleep(backoff_seconds[min(attempt, len(backoff_seconds) - 1)])
                continue
            raise AuthError(
                last_message,
                transient=True,
                error_kind="network_error",
            ) from exc

        if response.ok:
            return response.json() if response.content else {}

        message, request_id = _extract_error_details(response)
        last_request_id = request_id or last_request_id
        last_message = message
        is_transient = _is_transient_http_error(response.status_code, message)
        _auth_diag_log(
            "auth_request_http_error",
            method=method,
            path=path,
            grant_type=grant_type,
            retry_safe=retry_safe,
            attempt=attempt + 1,
            max_attempts=max_attempts,
            status_code=response.status_code,
            transient=is_transient,
            request_id=request_id or "",
            message=message[:280],
        )
        if retry_safe and is_transient and attempt < max_attempts - 1:
            time.sleep(backoff_seconds[min(attempt, len(backoff_seconds) - 1)])
            continue
        raise AuthError(
            message,
            request_id=request_id,
            status_code=response.status_code,
            transient=is_transient,
            error_kind="transient_http" if is_transient else "http_error",
        )

    raise AuthError(last_message, request_id=last_request_id, transient=True, error_kind="retry_exhausted")


def _auth_cookie_config() -> tuple[str | None, int]:
    cfg = st.secrets.get("auth", {})
    cookie_secret = str(cfg.get("cookie_secret") or "").strip()
    remember_days_raw = cfg.get("remember_days")
    try:
        remember_days = int(remember_days_raw) if remember_days_raw is not None else AUTH_REMEMBER_DAYS_DEFAULT
    except Exception:
        remember_days = AUTH_REMEMBER_DAYS_DEFAULT
    remember_days = max(1, remember_days)
    return (cookie_secret or None, remember_days)


def _auth_cookie_manager():
    if stx is None:
        return None
    try:
        return stx.CookieManager(key="supabase_auth_cookie_manager")
    except Exception:
        return None


def _b64url_encode(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).decode("utf-8").rstrip("=")


def _b64url_decode(data: str) -> bytes:
    padded = data + "=" * ((4 - len(data) % 4) % 4)
    return base64.urlsafe_b64decode(padded.encode("utf-8"))


def _build_signed_payload_cookie(payload: dict[str, Any], cookie_secret: str) -> str:
    payload_json = json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8")
    payload_b64 = _b64url_encode(payload_json)
    sig = hmac.new(cookie_secret.encode("utf-8"), payload_b64.encode("utf-8"), hashlib.sha256).digest()
    return f"{payload_b64}.{_b64url_encode(sig)}"


def _parse_signed_payload_cookie(cookie_value: str, cookie_secret: str) -> dict[str, Any] | None:
    token = str(cookie_value or "").strip()
    if "." not in token:
        return None
    payload_b64, sig_b64 = token.split(".", 1)
    try:
        expected_sig = hmac.new(
            cookie_secret.encode("utf-8"),
            payload_b64.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected_sig_b64 = _b64url_encode(expected_sig)
        if not hmac.compare_digest(expected_sig_b64, sig_b64):
            return None

        payload_raw = _b64url_decode(payload_b64)
        payload = json.loads(payload_raw.decode("utf-8"))
        if not isinstance(payload, dict):
            return None
        return payload
    except Exception:
        return None


def _build_signed_auth_cookie(refresh_token: str, expires_at: int, cookie_secret: str) -> str:
    return _build_signed_payload_cookie({"rt": refresh_token, "exp": int(expires_at)}, cookie_secret)


def _parse_signed_auth_cookie(cookie_value: str, cookie_secret: str) -> tuple[str, int] | None:
    payload = _parse_signed_payload_cookie(cookie_value, cookie_secret)
    if not payload:
        return None
    try:
        refresh_token = str(payload.get("rt") or "").strip()
        expires_at = int(payload.get("exp") or 0)
        if not refresh_token or expires_at <= int(time.time()):
            return None
        return (refresh_token, expires_at)
    except Exception:
        return None


def _save_auth_cookie(refresh_token: str):
    cookie_secret, remember_days = _auth_cookie_config()
    if not cookie_secret:
        return
    cookie_manager = _auth_cookie_manager()
    if cookie_manager is None:
        return

    now_ts = int(time.time())
    cookie_exp_ts = now_ts + remember_days * 24 * 60 * 60
    signed_value = _build_signed_auth_cookie(refresh_token, cookie_exp_ts, cookie_secret)
    expires_at = dt.datetime.fromtimestamp(cookie_exp_ts, tz=dt.timezone.utc).replace(tzinfo=None)
    try:
        cookie_manager.set(
            AUTH_PERSIST_COOKIE_NAME,
            signed_value,
            expires_at=expires_at,
            key=f"{AUTH_PERSIST_COOKIE_NAME}_set",
        )
    except Exception:
        return


def _load_auth_cookie() -> str | None:
    cookie_secret, _ = _auth_cookie_config()
    if not cookie_secret:
        return None
    cookie_manager = _auth_cookie_manager()
    if cookie_manager is None:
        return None

    try:
        cookie_value = cookie_manager.get(AUTH_PERSIST_COOKIE_NAME)
    except Exception:
        return None
    if not cookie_value:
        return None

    parsed = _parse_signed_auth_cookie(str(cookie_value), cookie_secret)
    if not parsed:
        _clear_auth_cookie()
        return None
    refresh_token, _ = parsed
    return refresh_token


def _clear_auth_cookie():
    cookie_manager = _auth_cookie_manager()
    if cookie_manager is None:
        return
    try:
        cookie_manager.delete(
            AUTH_PERSIST_COOKIE_NAME,
            key=f"{AUTH_PERSIST_COOKIE_NAME}_delete",
        )
    except Exception:
        return


def _save_oauth_flow(flow_id: str, code_verifier: str) -> bool:
    expires_at_ts = int(time.time()) + AUTH_OAUTH_FLOW_TTL_SECONDS
    flow_payload = {
        "flow_id": str(flow_id or ""),
        "code_verifier": str(code_verifier or ""),
        "exp": expires_at_ts,
    }
    st.session_state[AUTH_OAUTH_FLOW_KEY] = flow_payload

    cookie_secret, _ = _auth_cookie_config()
    cookie_manager = _auth_cookie_manager()
    if not cookie_secret or cookie_manager is None:
        return False

    signed_value = _build_signed_payload_cookie(flow_payload, cookie_secret)
    expires_at = dt.datetime.fromtimestamp(expires_at_ts, tz=dt.timezone.utc).replace(tzinfo=None)
    try:
        cookie_manager.set(
            AUTH_OAUTH_FLOW_COOKIE_NAME,
            signed_value,
            expires_at=expires_at,
            key=f"{AUTH_OAUTH_FLOW_COOKIE_NAME}_set",
        )
    except Exception:
        return False
    return True


def _clear_oauth_flow():
    st.session_state.pop(AUTH_OAUTH_FLOW_KEY, None)
    cookie_manager = _auth_cookie_manager()
    if cookie_manager is None:
        return
    try:
        cookie_manager.delete(
            AUTH_OAUTH_FLOW_COOKIE_NAME,
            key=f"{AUTH_OAUTH_FLOW_COOKIE_NAME}_delete",
        )
    except Exception:
        return


def _oauth_flow_payload_matches(payload: dict[str, Any] | None, flow_id: str) -> str | None:
    if not isinstance(payload, dict):
        return None
    try:
        expires_at = int(payload.get("exp") or 0)
    except Exception:
        expires_at = 0
    if expires_at <= int(time.time()):
        return None
    if not hmac.compare_digest(str(payload.get("flow_id") or ""), str(flow_id or "")):
        return None
    code_verifier = str(payload.get("code_verifier") or "").strip()
    return code_verifier or None


def _load_oauth_code_verifier(flow_id: str, fallback_code_verifier: str = "") -> str | None:
    fallback = str(fallback_code_verifier or "").strip()
    if fallback:
        _auth_diag_log("google_oauth_code_verifier_fallback_query_param", flow_id=flow_id)
        return fallback

    session_verifier = _oauth_flow_payload_matches(
        st.session_state.get(AUTH_OAUTH_FLOW_KEY),
        flow_id,
    )
    if session_verifier:
        return session_verifier

    cookie_secret, _ = _auth_cookie_config()
    cookie_manager = _auth_cookie_manager()
    if not cookie_secret or cookie_manager is None:
        return None

    try:
        cookie_value = cookie_manager.get(AUTH_OAUTH_FLOW_COOKIE_NAME)
    except Exception:
        return None
    if not cookie_value:
        return None

    cookie_payload = _parse_signed_payload_cookie(str(cookie_value), cookie_secret)
    cookie_verifier = _oauth_flow_payload_matches(cookie_payload, flow_id)
    if cookie_verifier:
        return cookie_verifier

    _clear_oauth_flow()
    return None


def _store_session(payload: dict[str, Any], *, persist_cookie: bool = True):
    expires_at = payload.get("expires_at")
    if not expires_at:
        expires_in = int(payload.get("expires_in") or 3600)
        expires_at = int(time.time()) + expires_in

    session = {
        "access_token": payload.get("access_token"),
        "refresh_token": payload.get("refresh_token"),
        "expires_at": int(expires_at),
        "user": payload.get("user") or {},
    }
    st.session_state[AUTH_SESSION_KEY] = session
    refresh_token = str(session.get("refresh_token") or "").strip()
    if persist_cookie and refresh_token:
        _save_auth_cookie(refresh_token)


def clear_auth_session(*, clear_cookie: bool = True):
    st.session_state.pop(AUTH_SESSION_KEY, None)
    if clear_cookie:
        _clear_auth_cookie()


def get_session_user() -> dict[str, Any] | None:
    session = st.session_state.get(AUTH_SESSION_KEY)
    if not isinstance(session, dict):
        return None
    user = session.get("user")
    return user if isinstance(user, dict) else None


def get_session_user_id() -> str:
    user = get_session_user() or {}
    return str(user.get("id") or "anonymous")


def _refresh_session() -> dict[str, Any] | None:
    session = st.session_state.get(AUTH_SESSION_KEY)
    if not isinstance(session, dict):
        return None

    refresh_token = str(session.get("refresh_token") or "").strip()
    if not refresh_token:
        clear_auth_session(clear_cookie=True)
        return None

    refreshed = _auth_request(
        "POST",
        "token",
        params={"grant_type": "refresh_token"},
        payload={"refresh_token": refresh_token},
    )
    if not refreshed.get("user"):
        refreshed["user"] = session.get("user") or {}
    _store_session(refreshed, persist_cookie=True)
    return st.session_state.get(AUTH_SESSION_KEY)


def _restore_session_from_cookie() -> dict[str, Any] | None:
    if isinstance(st.session_state.get(AUTH_SESSION_KEY), dict):
        return st.session_state.get(AUTH_SESSION_KEY)

    refresh_token = _load_auth_cookie()
    if not refresh_token:
        return None

    try:
        refreshed = _auth_request(
            "POST",
            "token",
            params={"grant_type": "refresh_token"},
            payload={"refresh_token": refresh_token},
        )
    except AuthError as exc:
        request_id = str(getattr(exc, "request_id", "") or "").strip() or None
        if _auth_error_is_transient(exc):
            _register_transient_auth_issue(
                reason=str(exc),
                request_id=request_id,
                issue_type="refresh_cookie_transient",
            )
            _auth_diag_log(
                "auth_cookie_restore_transient",
                request_id=request_id or "",
                error_kind=str(getattr(exc, "error_kind", "") or ""),
                message=str(exc)[:280],
            )
            return None
        clear_auth_session(clear_cookie=True)
        return None

    _store_session(refreshed, persist_cookie=True)
    return st.session_state.get(AUTH_SESSION_KEY)


def get_current_session() -> dict[str, Any] | None:
    session = st.session_state.get(AUTH_SESSION_KEY)
    if not isinstance(session, dict):
        return None

    access_token = str(session.get("access_token") or "").strip()
    if not access_token:
        clear_auth_session(clear_cookie=True)
        return None

    expires_at = int(session.get("expires_at") or 0)
    if expires_at and expires_at <= int(time.time()) + 60:
        try:
            session = _refresh_session()
        except AuthError as exc:
            request_id = str(getattr(exc, "request_id", "") or "").strip() or None
            if _auth_error_is_transient(exc):
                _register_transient_auth_issue(
                    reason=str(exc),
                    request_id=request_id,
                    issue_type="refresh_token_transient",
                )
                _auth_diag_log(
                    "auth_session_refresh_transient",
                    request_id=request_id or "",
                    error_kind=str(getattr(exc, "error_kind", "") or ""),
                    expires_at=expires_at,
                    message=str(exc)[:280],
                )
                if expires_at > int(time.time()) + 5:
                    return session
                return None
            clear_auth_session(clear_cookie=True)
            return None

    return session


def sign_in_with_password(email: str, password: str) -> dict[str, Any]:
    email_clean = str(email or "").strip()
    password_clean = str(password or "")
    if not email_clean or not password_clean:
        raise AuthError("Enter both email and password.")

    payload = _auth_request(
        "POST",
        "token",
        params={"grant_type": "password"},
        payload={"email": email_clean, "password": password_clean},
    )
    _store_session(payload, persist_cookie=True)
    return payload.get("user") or {}


def _query_param(name: str) -> str:
    value = st.query_params.get(name)
    if isinstance(value, list):
        return str(value[0]) if value else ""
    return str(value or "")


def _clear_oauth_query_params():
    try:
        st.query_params.clear()
        return
    except Exception:
        pass

    try:
        st.experimental_set_query_params()
    except Exception:
        pass


def _set_flash_error(message: str):
    st.session_state[AUTH_FLASH_ERROR_KEY] = str(message)


def _consume_flash_error() -> str:
    return str(st.session_state.pop(AUTH_FLASH_ERROR_KEY, "") or "")


def _build_pkce_code_verifier() -> str:
    verifier = secrets.token_urlsafe(64)
    return verifier[:96]


def _build_pkce_code_challenge(code_verifier: str) -> str:
    digest = hashlib.sha256(code_verifier.encode("utf-8")).digest()
    return base64.urlsafe_b64encode(digest).decode("utf-8").rstrip("=")


def _build_google_redirect_url(flow_id: str, code_verifier: str) -> str:
    redirect_to = _oauth_app_url()
    separator = "&" if "?" in redirect_to else "?"
    verifier_saved = _save_oauth_flow(flow_id, code_verifier)
    query_params = {"google_flow_id": flow_id}
    if not verifier_saved:
        # Fallback for local/dev environments without the optional cookie component.
        query_params["google_code_verifier"] = code_verifier
    params = urlencode(query_params)
    _auth_diag_log(
        "google_oauth_redirect_url_prepared",
        flow_id=flow_id,
        verifier_storage="cookie_or_session" if verifier_saved else "query_param_fallback",
    )
    return f"{redirect_to}{separator}{params}"


def build_google_oauth_url() -> str:
    cfg = _auth_config()
    code_verifier = _build_pkce_code_verifier()
    flow_id = secrets.token_urlsafe(24)
    code_challenge = _build_pkce_code_challenge(code_verifier)

    redirect_to = _build_google_redirect_url(flow_id, code_verifier)
    _auth_diag_log(
        "google_oauth_start",
        redirect_to=_oauth_app_url(),
        flow_id=flow_id,
    )

    params = {
        "provider": "google",
        "redirect_to": redirect_to,
        "code_challenge": code_challenge,
        "code_challenge_method": "s256",
    }
    return f"{cfg['base_url']}/auth/v1/authorize?{urlencode(params)}"


def start_google_sign_in() -> str:
    return build_google_oauth_url()


def _exchange_google_code_for_session(auth_code: str, code_verifier: str) -> dict[str, Any]:
    return _auth_request(
        "POST",
        "token",
        params={"grant_type": "pkce"},
        payload={
            "auth_code": auth_code,
            "code_verifier": code_verifier,
        },
    )


def handle_oauth_callback() -> bool:
    code = _query_param("code")
    flow_id = _query_param("google_flow_id")
    fallback_code_verifier = _query_param("google_code_verifier")
    code_verifier = _load_oauth_code_verifier(flow_id, fallback_code_verifier) if flow_id else ""
    error = _query_param("error")
    error_description = _query_param("error_description")

    if not any((code, error, error_description)):
        return False

    _auth_diag_log(
        "google_oauth_callback_received",
        has_code=bool(code),
        has_flow_id=bool(flow_id),
        has_code_verifier=bool(code_verifier),
        has_query_param_verifier=bool(fallback_code_verifier),
        has_error=bool(error or error_description),
    )

    if code:
        last_code = str(st.session_state.get(AUTH_LAST_OAUTH_CODE_KEY) or "")
        if last_code and hmac.compare_digest(last_code, code):
            _auth_diag_log("google_oauth_callback_duplicate_code")
            _clear_oauth_query_params()
            _safe_rerun()
            return True

    if error:
        message = error_description or error or "Google sign-in was cancelled."
        _auth_diag_log("google_oauth_callback_provider_error", message=message)
        if _is_transient_auth_message(message) or "unable to exchange external code" in message.lower():
            _register_transient_auth_issue(
                reason=message,
                issue_type="external_code_exchange_failed",
            )
            _set_flash_error(
                "Google sign-in is temporarily degraded between Supabase and Google. "
                "Please wait 10-30 seconds and start a fresh Google sign-in flow."
            )
        else:
            _set_flash_error(message)
        _clear_oauth_flow()
        _clear_oauth_query_params()
        _safe_rerun()
        return True

    if not flow_id:
        _auth_diag_log("google_oauth_callback_missing_flow")
        _set_flash_error("Google sign-in flow state is missing. Please start a fresh Google sign-in flow.")
        _clear_oauth_flow()
        _clear_oauth_query_params()
        _safe_rerun()
        return True

    if not code_verifier or not code:
        _auth_diag_log("google_oauth_callback_missing_code_data")
        _set_flash_error("Google sign-in callback data is missing or expired. Please start a fresh Google sign-in flow.")
        _clear_oauth_flow()
        _clear_oauth_query_params()
        _safe_rerun()
        return True

    st.session_state[AUTH_LAST_OAUTH_CODE_KEY] = code

    try:
        payload = _exchange_google_code_for_session(code, code_verifier)
    except AuthError as exc:
        message = str(exc)
        request_id = str(getattr(exc, "request_id", "") or "").strip() or None
        lowered = message.lower()
        external_exchange_failed = "unable to exchange external code" in lowered
        is_transient = _auth_error_is_transient(exc) or external_exchange_failed
        is_invalid_grant = _auth_error_is_invalid_token(exc) and not is_transient

        if is_transient:
            _register_transient_auth_issue(
                reason=message,
                request_id=request_id,
                issue_type="external_code_exchange_failed" if external_exchange_failed else "pkce_exchange_transient",
            )
            _set_flash_error(
                _append_request_id(
                    "Google sign-in is temporarily unavailable between Supabase and Google. "
                    "Please wait 10-30 seconds and start a fresh Google sign-in flow.",
                    request_id,
                )
            )
        elif is_invalid_grant:
            _set_flash_error(
                _append_request_id(
                    "Google sign-in code expired, was already used, or the flow state was lost. "
                    "Please start a fresh Google sign-in flow.",
                    request_id,
                )
            )
        else:
            _set_flash_error(_append_request_id(f"Google sign-in failed: {message}", request_id))

        _auth_diag_log(
            "google_oauth_callback_exchange_failed",
            transient=is_transient,
            invalid_grant=is_invalid_grant,
            external_exchange_failed=external_exchange_failed,
            request_id=request_id or "",
            error_kind=str(getattr(exc, "error_kind", "") or ""),
            message=message[:300],
        )
        _clear_oauth_flow()
        _clear_oauth_query_params()
        _safe_rerun()
        return True

    _store_session(payload, persist_cookie=True)
    _clear_auth_degraded_state()
    _clear_oauth_flow()
    _auth_diag_log("google_oauth_callback_success")
    _clear_oauth_query_params()
    _safe_rerun()
    return True


def logout():
    session = st.session_state.get(AUTH_SESSION_KEY)
    access_token = ""
    if isinstance(session, dict):
        access_token = str(session.get("access_token") or "").strip()

    if access_token:
        try:
            _auth_request("POST", "logout", access_token=access_token)
        except AuthError:
            pass

    clear_auth_session(clear_cookie=True)


def _render_login_screen(page_label: str | None = None):
    flash_error = _consume_flash_error()
    if "auth_terms_accepted" not in st.session_state:
        st.session_state["auth_terms_accepted"] = True

    terms_accepted = st.session_state.get("auth_terms_accepted", True)

    st.title("Secure Sign In")
    if page_label:
        header_text = (
            f"Sign in to access {page_label} app. "
            "Authentication is required before market data can be accessed."
        )
    else:
        header_text = (
            "Log in to access this page. "
            "Authentication is required before market data can be accessed."
        )
    st.markdown(
        f"<p style='margin: 0 0 0.75rem 0; color: #9ca3af;'>{header_text}</p>",
        unsafe_allow_html=True,
    )

    google_cooldown_remaining = 0
    degraded = st.session_state.get(AUTH_DEGRADED_KEY)
    if isinstance(degraded, dict):
        try:
            age_seconds = max(0.0, float(time.time()) - float(degraded.get("epoch") or 0.0))
        except Exception:
            age_seconds = 10**9
        if age_seconds <= 30 * 60:
            count_10m = int(degraded.get("count_10m") or 0)
            request_id = str(degraded.get("request_id") or "").strip()
            issue_type = str(degraded.get("issue_type") or "transient")
            google_cooldown_remaining = max(
                0,
                int(AUTH_GOOGLE_RETRY_AFTER_SECONDS - age_seconds),
            )
            base_msg = (
                "Auth may be temporarily degraded (Supabase/Google upstream). "
                "If Google sign-in fails, wait 10-30 seconds and start a fresh sign-in flow."
            )
            if count_10m >= 3:
                base_msg += " Multiple transient failures detected in the last 10 minutes. Prefer retry-later over repeated rapid clicks."
            st.warning(_append_request_id(base_msg, request_id))
            with st.expander("Auth diagnostic details", expanded=False):
                st.json(
                    {
                        "type": issue_type,
                        "request_id": request_id,
                        "count_10m": count_10m,
                        "age_seconds": round(age_seconds, 1),
                        "suggestion": (
                            "wait_and_retry_later"
                            if issue_type.endswith("transient") or "external_code" in issue_type
                            else "retry_fresh_flow"
                        ),
                        "reason": str(degraded.get("reason") or "")[:500],
                    }
                )

    with st.expander("Access Options", expanded=True):
        st.markdown(
            "- **Google Sign-In**: Recommended for self-service access and the fastest way to get started. If you have previously used Google to access the platform, continue with the same option.\n"
            "- **Email and Password**: Available for accounts provisioned by the application owner. If this is your first login with email, please contact the owner to have credentials assigned to your address."
        )

    with st.expander("Privacy Notice and Terms of Use", expanded=False):
        st.markdown(
            "**Data Controller**: Michal Ostaszewski, contact: michael@cosmonity.com\n\n"
            "This application is currently a non-commercial project created for knowledge sharing, research, and experimentation.\n\n"
            "**Use of the App**\n"
            "- Access to the application is voluntary.\n"
            "- The content is provided for informational and educational purposes only.\n"
            "- Any decisions made on the basis of the data, forecasts, or analytics presented in the application are made at your own risk and responsibility.\n\n"
            "**Personal Data and Authentication**\n"
            "- To provide secure access, the application processes basic authentication data such as your email address and login provider information.\n"
            "- Outside of authentication and technical access control, the application does not currently collect additional personal data for marketing purposes.\n"
            "- At present, your data is not used for marketing campaigns. In the future, contact details may be used to send updates, information, or offers related to this application.\n\n"
            "**Cookies and Technical Storage**\n"
            "- The application does not currently use advertising cookies or analytics cookies.\n"
            "- Essential technical storage mechanisms may still be used by Streamlit, Supabase Auth, or Google Sign-In to support secure login and session handling.\n\n"
            "**Project Status**\n"
            "- This is not currently a commercial service.\n"
            "- The application may be modified, limited, or discontinued at any time."
        )

    terms_accepted = st.checkbox(
        "I have read and accept the Privacy Notice and Terms of Use.",
        key="auth_terms_accepted",
    )

    if flash_error:
        st.error(flash_error)

    st.markdown(
        """
        <style>
        .auth-google-button {
            display: block;
            width: 100%;
            text-align: center;
            padding: 0.72rem 1rem;
            border-radius: 0.65rem;
            background: linear-gradient(180deg, #3b82f6 0%, #2563eb 100%);
            color: #ffffff !important;
            text-decoration: none !important;
            font-weight: 600;
            box-shadow: 0 8px 20px rgba(37, 99, 235, 0.28);
            margin: 0.15rem 0 0;
        }
        .auth-google-button:hover {
            background: linear-gradient(180deg, #4f8ff8 0%, #1d4ed8 100%);
            color: #ffffff !important;
        }
        .auth-google-button-disabled {
            display: block;
            width: 100%;
            text-align: center;
            padding: 0.72rem 1rem;
            border-radius: 0.65rem;
            background: #29415f;
            color: #cbd5e1;
            border: 1px solid rgba(148, 163, 184, 0.2);
            font-weight: 600;
            margin: 0.15rem 0 0;
        }
        .auth-google-recommendation {
            margin: 0.45rem 0 0.8rem 0;
            color: #bfdbfe;
            font-size: 0.92rem;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("##### Google Sign-In")

    if not terms_accepted:
        st.markdown(
            "<div class='auth-google-button-disabled'>Sign in with Google</div>",
            unsafe_allow_html=True,
        )
        st.caption("Accept the Privacy Notice and Terms of Use to continue.")
    elif google_cooldown_remaining > 0:
        st.markdown(
            "<div class='auth-google-button-disabled'>Sign in with Google</div>",
            unsafe_allow_html=True,
        )
        st.caption(
            f"Google Auth was just degraded. Wait about {google_cooldown_remaining}s before starting a fresh flow."
        )
    else:
        try:
            redirect_url = start_google_sign_in()
        except AuthError as exc:
            st.error(f"Google sign-in setup error: {exc}")
        else:
            st.markdown(
                f"<a class='auth-google-button' href='{redirect_url}' target='_self'>Sign in with Google</a>",
                unsafe_allow_html=True,
            )

    st.markdown(
        "<div class='auth-google-recommendation'>Recommended: use Google Sign-In for the quickest and simplest access.</div>",
        unsafe_allow_html=True,
    )

    with st.expander("Email and Password", expanded=False):
        st.caption("Alternative sign-in option for accounts provisioned directly by the application owner. To obtain credentials, please contact me at michael@cosmonity.com.")
        with st.form("supabase_login_form", clear_on_submit=False):
            email = st.text_input("Email", autocomplete="email")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button(
                "Sign in with email",
                type="primary",
                use_container_width=True,
            )

        if submitted:
            if not terms_accepted:
                st.error("Please review and accept the Privacy Notice and Terms of Use before signing in.")
                return
            try:
                user = sign_in_with_password(email, password)
            except AuthError as exc:
                st.error(f"Sign-in failed: {exc}")
            else:
                st.success(f"Signed in as {user.get('email', 'user')}.")
                _safe_rerun()


def _render_auth_sidebar():
    user = get_session_user() or {}
    email = user.get("email") or "signed-in user"
    with st.sidebar:
        st.markdown("---")
        st.caption(f"Signed in as {email}")
        if st.button("Log out", key="app_auth_logout", use_container_width=True):
            logout()
            _safe_rerun()


def require_auth(page_label: str | None = None) -> dict[str, Any]:
    try:
        session = get_current_session()
    except AuthError as exc:
        st.error(str(exc))
        st.stop()

    if session:
        _render_auth_sidebar()
        return session.get("user") or {}

    if handle_oauth_callback():
        st.stop()

    try:
        session = _restore_session_from_cookie()
    except AuthError as exc:
        st.error(str(exc))
        st.stop()
    if session:
        _render_auth_sidebar()
        return session.get("user") or {}

    _render_login_screen(page_label=page_label)
    st.stop()
