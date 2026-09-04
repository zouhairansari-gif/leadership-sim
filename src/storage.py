"""Session persistence.

JSON-file storage, one file per session. This decouples the reviewer page
from the candidate's live Streamlit session state — a reviewer opens the
dossier after the candidate is long gone, from a different browser session.

This is a skeleton, not a production store: no concurrency handling, no
auth, no encryption at rest. Swap for a real database before this ever
touches a real candidate's data — remember Session data is exactly the
kind of thing the EU AI Act's logging/documentation obligations apply to.
"""
from __future__ import annotations

import json
import os

DATA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "data", "sessions")


def _path(session_id: str) -> str:
    os.makedirs(DATA_DIR, exist_ok=True)
    return os.path.join(DATA_DIR, f"{session_id}.json")


def save_session(session_id: str, data: dict) -> None:
    with open(_path(session_id), "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)


def load_session(session_id: str) -> dict:
    with open(_path(session_id), "r", encoding="utf-8") as f:
        return json.load(f)


def list_session_ids() -> list[str]:
    os.makedirs(DATA_DIR, exist_ok=True)
    return sorted(
        fn[:-5] for fn in os.listdir(DATA_DIR) if fn.endswith(".json")
    )


def list_sessions_with_meta() -> list[dict]:
    """Lightweight listing for the reviewer page's candidate grouping and
    pilot-run filter. Loads each file fully (fine at this scale — this is a
    skeleton storage layer, see the module docstring) but only returns the
    fields needed to build the picker, not full transcripts."""
    out = []
    for sid in list_session_ids():
        try:
            data = load_session(sid)
        except (json.JSONDecodeError, OSError):
            continue
        out.append({
            "session_id": data.get("session_id", sid),
            "candidate_id": data.get("candidate_id", "Unknown candidate"),
            "is_pilot": data.get("is_pilot", False),
            "finished": data.get("finished", False),
        })
    return out
