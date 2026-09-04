"""Canonical sessions. A session chains scenario ("beat") ids with shared
agents and state. This is the actual product unit — standalone beats exist
as scenario files, but candidates run sessions.

Add new sessions here as plain data. Don't scatter session composition
logic elsewhere.
"""

SESSION_A = {
    "id": "session_a",
    "title": "The Week With Amara",
    "beats": [
        "beat0_warmup",
        "beat1_deadline",
        "beat2_farhans_dip",
        "beat3_senior_stakeholder",
        "beat4_debrief",
    ],
    # Which beat pairs get diffed against each other by the evaluator,
    # rather than scored standalone.
    "asymmetry_pairs": [("beat2_farhans_dip", "beat3_senior_stakeholder")],
    # Which beat is the narrative-integrity debrief, checked against all
    # beats before it.
    "debrief_beat": "beat4_debrief",
    # Narrative bridge shown between this session and the next one in
    # SESSION_SEQUENCE — same visual language as a beat transition
    # (render_transition), so moving from Session A into Session B feels
    # continuous rather than like restarting the app.
    "transition_to_next": "Weeks pass. A new quarter is closing.",
}

SESSION_B = {
    "id": "session_b",
    "title": "The Quarter-End Number",
    "beats": [
        "beat0_warmup",
        "sessionb_beat1_dissent",
        "sessionb_beat2_resource_conflict",
        "sessionb_beat3_misreport",
        "sessionb_beat4_debrief",
    ],
    # No asymmetry pair here — Session B's mechanic is propagation (does a
    # private compromise in Beat 3 survive being restated upward in Beat 4),
    # not a same-substance/different-power-distance diff like Session A's.
    "asymmetry_pairs": [],
    "debrief_beat": "sessionb_beat4_debrief",
    "transition_to_next": "Months later, a new project takes shape.",
}

SESSION_C = {
    "id": "session_c",
    "title": "The Long Game",
    "beats": [
        "beat0_warmup",
        "sessionc_beat1_development",
        "sessionc_beat2_credit",
        "sessionc_beat3_absent_colleague",
        "sessionc_beat4_debrief",
    ],
    "asymmetry_pairs": [],
    "debrief_beat": "sessionc_beat4_debrief",
    # Nothing comes after Session C yet.
}

ALL_SESSIONS = {SESSION_A["id"]: SESSION_A, SESSION_B["id"]: SESSION_B, SESSION_C["id"]: SESSION_C}

# Defines what "next" means for the smooth-continuation flow — deliberately
# separate from ALL_SESSIONS (a dict has no inherent order) and from each
# session's own config (a session shouldn't need to know its position in a
# sequence to be valid standalone, e.g. for future pilot-only or
# out-of-order use).
SESSION_SEQUENCE = [SESSION_A["id"], SESSION_B["id"], SESSION_C["id"]]


def get_session_config(session_id: str) -> dict:
    return ALL_SESSIONS[session_id]


def get_next_session_id(current_session_id: str) -> str | None:
    """None means there's nothing to continue into — end the sitting here."""
    try:
        idx = SESSION_SEQUENCE.index(current_session_id)
    except ValueError:
        return None
    return SESSION_SEQUENCE[idx + 1] if idx + 1 < len(SESSION_SEQUENCE) else None
