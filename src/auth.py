"""Shared password gate.

Deliberately simple: one shared password, not per-user accounts — this
matches where the project actually is (a pilot tool for a known group of
people), not a multi-tenant product. If real per-person access control is
ever needed, Streamlit Community Cloud's own private-app/email-allowlist
feature is the right upgrade path, not a bigger version of this file.

Called at the top of EVERY page (app.py and every file in pages/), right
after that page's own st.set_page_config call. Streamlit only shares
session state across pages reached via in-app navigation — a bookmarked
or shared link straight to a sub-page loads fresh and skips whatever ran
in app.py, so each page needs its own call to this function, not just the
entrypoint.
"""
import os


def _get_password(st) -> str | None:
    """Checks os.environ first (works locally via .env, and Streamlit
    Community Cloud mirrors secrets.toml into the environment too), with a
    direct st.secrets fallback in case that mirroring isn't available in a
    given Streamlit version — this is the one place in the app worth that
    extra defensiveness, since a silently-missing password check is a real
    security gap, not just a broken feature."""
    val = os.environ.get("APP_PASSWORD")
    if val:
        return val
    try:
        return st.secrets.get("APP_PASSWORD")
    except Exception:
        return None


def require_password(st) -> None:
    """No-op if APP_PASSWORD isn't configured — that's the right default
    for local development, but it also means deployment ALWAYS needs this
    secret set, or the app runs fully open. Worth checking it's actually
    set after deploying, not just assuming."""
    app_password = _get_password(st)
    if not app_password:
        return

    if st.session_state.get("authenticated"):
        return

    st.title("Sign in")
    entered = st.text_input("Password", type="password", key="password_gate_input")
    if st.button("Enter"):
        if entered == app_password:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Incorrect password.")
    st.stop()
