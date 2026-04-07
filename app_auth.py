from __future__ import annotations

import base64
import hashlib
import secrets
import time
from typing import Any
from urllib.parse import urlencode, urlsplit, urlunsplit

import requests
import streamlit as st


AUTH_SESSION_KEY = "supabase_auth_session"
AUTH_FLASH_ERROR_KEY = "supabase_auth_flash_error"
GOOGLE_FLOW_TTL_SECONDS = 900


class AuthError(RuntimeError):
    pass


def _safe_rerun():
    try:
        st.rerun()
    except Exception:
        if hasattr(st, "experimental_rerun"):
            st.experimental_rerun()


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


def _oauth_app_url() -> str:
    try:
        current_url = str(getattr(st.context, "url", "") or "").strip()
    except Exception:
        current_url = ""

    normalized_current_url = _normalize_public_url(current_url)
    if normalized_current_url:
        return normalized_current_url

    try:
        host = str(st.context.headers.get("host") or "").strip()
    except Exception:
        host = ""

    if host:
        scheme = "http" if host.startswith(("localhost", "127.0.0.1")) else "https"
        normalized_host_url = _normalize_public_url(f"{scheme}://{host}")
        if normalized_host_url:
            return normalized_host_url

    cfg = st.secrets.get("supabase_auth", {})
    local_app_url = _normalize_public_url(str(cfg.get("local_app_url") or ""))
    if local_app_url:
        return local_app_url

    app_url = _normalize_public_url(str(cfg.get("app_url") or ""))
    if app_url:
        return app_url

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

    response = requests.request(
        method=method,
        url=f"{cfg['base_url']}/auth/v1/{path.lstrip('/')}",
        params=params,
        json=payload,
        headers=headers,
        timeout=15,
    )

    if response.ok:
        return response.json() if response.content else {}

    message = "Supabase Auth request failed."
    try:
        body = response.json()
        message = (
            body.get("msg")
            or body.get("message")
            or body.get("error_description")
            or body.get("error")
            or message
        )
    except ValueError:
        if response.text.strip():
            message = response.text.strip()

    raise AuthError(message)


def _store_session(payload: dict[str, Any]):
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


def clear_auth_session():
    st.session_state.pop(AUTH_SESSION_KEY, None)


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
        clear_auth_session()
        return None

    refreshed = _auth_request(
        "POST",
        "token",
        params={"grant_type": "refresh_token"},
        payload={"refresh_token": refresh_token},
    )
    if not refreshed.get("user"):
        refreshed["user"] = session.get("user") or {}
    _store_session(refreshed)
    return st.session_state.get(AUTH_SESSION_KEY)


def get_current_session() -> dict[str, Any] | None:
    session = st.session_state.get(AUTH_SESSION_KEY)
    if not isinstance(session, dict):
        return None

    access_token = str(session.get("access_token") or "").strip()
    if not access_token:
        clear_auth_session()
        return None

    expires_at = int(session.get("expires_at") or 0)
    if expires_at and expires_at <= int(time.time()) + 60:
        try:
            session = _refresh_session()
        except AuthError:
            clear_auth_session()
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
    _store_session(payload)
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


@st.cache_resource
def _google_oauth_flow_store() -> dict[str, dict[str, Any]]:
    return {}


def _cleanup_google_oauth_flows():
    store = _google_oauth_flow_store()
    now = int(time.time())
    expired_states = [
        state
        for state, payload in store.items()
        if int(payload.get("created_at") or 0) < now - GOOGLE_FLOW_TTL_SECONDS
    ]
    for state in expired_states:
        store.pop(state, None)


def _store_google_oauth_flow(state: str, code_verifier: str):
    _cleanup_google_oauth_flows()
    _google_oauth_flow_store()[state] = {
        "code_verifier": code_verifier,
        "created_at": int(time.time()),
    }


def _pop_google_oauth_flow(state: str) -> dict[str, Any] | None:
    _cleanup_google_oauth_flows()
    return _google_oauth_flow_store().pop(state, None)


def build_google_oauth_url() -> str:
    cfg = _auth_config()
    redirect_to = _oauth_app_url()
    code_verifier = _build_pkce_code_verifier()
    state = secrets.token_urlsafe(32)
    code_challenge = _build_pkce_code_challenge(code_verifier)

    _store_google_oauth_flow(state, code_verifier)

    params = {
        "provider": "google",
        "redirect_to": redirect_to,
        "code_challenge": code_challenge,
        "code_challenge_method": "s256",
        "state": state,
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
    state = _query_param("state")
    error = _query_param("error")
    error_description = _query_param("error_description")

    if not any((code, error, error_description)):
        return False

    if error:
        message = error_description or error or "Google sign-in was cancelled."
        _set_flash_error(message)
        _clear_oauth_query_params()
        _safe_rerun()
        return True

    flow = _pop_google_oauth_flow(state)
    if not isinstance(flow, dict):
        _set_flash_error("Missing Google sign-in state. Start the Google flow again.")
        _clear_oauth_query_params()
        _safe_rerun()
        return True

    if not state:
        _set_flash_error("Google sign-in state mismatch. Start the Google flow again.")
        _clear_oauth_query_params()
        _safe_rerun()
        return True

    code_verifier = str(flow.get("code_verifier") or "")
    if not code_verifier or not code:
        _set_flash_error("Missing OAuth callback data. Start the Google flow again.")
        _clear_oauth_query_params()
        _safe_rerun()
        return True

    try:
        payload = _exchange_google_code_for_session(code, code_verifier)
    except AuthError as exc:
        _set_flash_error(f"Google sign-in failed: {exc}")
        _clear_oauth_query_params()
        _safe_rerun()
        return True

    _store_session(payload)
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

    clear_auth_session()


def _render_login_screen(page_label: str | None = None):
    flash_error = _consume_flash_error()

    st.title("Sign in required")
    if page_label:
        st.caption(f"Log in to access {page_label}.")
    else:
        st.caption("Log in to access this page.")

    st.info(
        "This app now requires authentication before any market data is loaded. "
        "You can sign in with Google or with an owner-provisioned email/password account."
    )

    if flash_error:
        st.error(flash_error)

    with st.form("supabase_login_form", clear_on_submit=False):
        email = st.text_input("Email", autocomplete="email")
        password = st.text_input("Password", type="password", autocomplete="current-password")
        submitted = st.form_submit_button("Sign in", use_container_width=True)

    if submitted:
        try:
            user = sign_in_with_password(email, password)
        except AuthError as exc:
            st.error(f"Sign-in failed: {exc}")
        else:
            st.success(f"Signed in as {user.get('email', 'user')}.")
            _safe_rerun()

    st.markdown(
        "<div style='text-align:center; margin: 0.75rem 0 0.5rem 0; color: #9ca3af;'>or</div>",
        unsafe_allow_html=True,
    )

    try:
        redirect_url = start_google_sign_in()
    except AuthError as exc:
        st.error(f"Google sign-in setup error: {exc}")
    else:
        if hasattr(st, "link_button"):
            st.link_button(
                "Sign in with Google",
                redirect_url,
                use_container_width=True,
            )
        else:
            st.markdown(f"[Sign in with Google]({redirect_url})")


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

    _render_login_screen(page_label=page_label)
    st.stop()
