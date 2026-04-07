from __future__ import annotations

import time
from typing import Any

import requests
import streamlit as st


AUTH_SESSION_KEY = "supabase_auth_session"


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
    st.title("Sign in required")
    if page_label:
        st.caption(f"Log in to access {page_label}.")
    else:
        st.caption("Log in to access this page.")

    st.info(
        "This app now requires a Supabase Auth account before any market data is loaded. "
        "Accounts are provisioned by the app owner."
    )

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

    _render_login_screen(page_label=page_label)
    st.stop()
