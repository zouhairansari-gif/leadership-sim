"""Leadership Simulation — candidate-facing app.

Runs a canonical session ("The Week With Amara" / "The Quarter-End Number")
beat by beat through the orchestrator, and — if the candidate finishes
Session A — offers a smooth, in-fiction continuation straight into
Session B rather than dropping them back to a cold start screen. The
candidate never sees agent rosters, dimensions, scores, or beat counts —
see src/ui_style.py and the design notes there for why.
"""
import os
import uuid

import streamlit as st
from dotenv import load_dotenv

from src.agents import AgentResponseError
from src.auth import require_password
from src.orchestrator import Session
from src.scenario import get_scenario
from src.session_config import ALL_SESSIONS, SESSION_A, get_next_session_id, get_session_config
from src.storage import save_session
from src.ui_style import (
    inject_css, render_agent_header, render_briefing,
    render_error_notice, render_thread, render_transition, render_typing_indicator,
)

load_dotenv()

st.set_page_config(page_title="Leadership Simulation", layout="centered")
require_password(st)
inject_css(st)

if not os.environ.get("ANTHROPIC_API_KEY"):
    st.error("Set ANTHROPIC_API_KEY in your .env file (see .env.example).")
    st.stop()


def _start_session(session_id: str) -> None:
    """Begins a fresh Session object while preserving candidate identity
    across a same-sitting continuation (see the done-screen logic below).
    Not used for the very first session — that path also needs to collect
    candidate_id/is_pilot, which live inline in the start-screen block."""
    st.session_state.session_run_id = f"{session_id}_{uuid.uuid4().hex[:8]}"
    st.session_state.orch = Session.start(session_id)
    st.session_state.phase = "chat"
    st.session_state.saved = False
    st.session_state.revealed_beats = set()


# ---------------------------------------------------------------- start screen
if "orch" not in st.session_state:
    st.title("Leadership Simulation")
    st.write(
        "This session takes about 30–40 minutes and consists of a series of "
        "workplace conversations. Your responses will be used to evaluate "
        "leadership and decision-making behavior as part of this process. "
        "There's nothing to prepare — just respond as you naturally would."
    )
    consent = st.checkbox("I understand and agree to proceed on this basis.")

    with st.expander("Running this as a calibration or practice session?"):
        is_pilot = st.checkbox(
            "This is a practice/calibration run, not a real candidate.",
            help="Marks the record accordingly so reviewers can filter it out "
                 "of real candidate results.",
        )

    candidate_id = st.text_input("Candidate identifier (for the reviewer record)")

    session_titles = {sid: cfg["title"] for sid, cfg in ALL_SESSIONS.items()}
    chosen_session_id = st.selectbox(
        "Session",
        options=list(session_titles.keys()),
        format_func=lambda sid: session_titles[sid],
        index=list(session_titles.keys()).index(SESSION_A["id"]),
    )

    can_begin = consent and bool(candidate_id.strip())
    if st.button("Begin session", disabled=not can_begin):
        st.session_state.candidate_id = candidate_id.strip()
        st.session_state.is_pilot = is_pilot
        _start_session(chosen_session_id)
        st.rerun()
    st.stop()

orch: Session = st.session_state.orch

# ---------------------------------------------------------------- done screen
if orch.finished:
    if not st.session_state.get("saved"):
        data = orch.to_dict()
        data["session_id"] = st.session_state.session_run_id
        data["candidate_id"] = st.session_state.candidate_id
        data["is_pilot"] = st.session_state.get("is_pilot", False)
        save_session(st.session_state.session_run_id, data)
        st.session_state.saved = True

    next_session_id = get_next_session_id(orch.config["id"])

    if next_session_id and not st.session_state.get("declined_next_session"):
        # Smooth, in-fiction continuation — same visual language as a beat
        # transition, not a dead end that forces a cold restart of consent
        # and candidate-ID entry. Still leaves an explicit way out; nobody
        # gets funneled into a second session against their will.
        render_transition(st, orch.config.get("transition_to_next", "Time passes."))
        col1, col2 = st.columns([2, 1])
        with col1:
            if st.button("Continue", type="primary"):
                _start_session(next_session_id)
                st.rerun()
        with col2:
            if st.button("I'm finished for now"):
                st.session_state.declined_next_session = True
                st.rerun()
        st.stop()

    st.title("Session complete")
    st.write("Thanks — that's everything for this sitting. You can close this tab.")
    st.stop()

scenario = orch.current_scenario
is_debrief = scenario.register == "debrief"

# ---------------------------------------------------------------- transition
if st.session_state.get("phase") == "transition":
    render_transition(st, scenario.transition_text)
    if st.button("Continue"):
        st.session_state.phase = "chat"
        st.rerun()
    st.stop()

# ---------------------------------------------------------------- chat
primary = scenario.primary_agent
beat = orch.current_beat

if "revealed_beats" not in st.session_state:
    st.session_state.revealed_beats = set()
is_first_view_of_beat = scenario.id not in st.session_state.revealed_beats
st.session_state.revealed_beats.add(scenario.id)

render_briefing(st, scenario.candidate_briefing.strip(), animate=is_first_view_of_beat)

with st.container():
    st.markdown('<div class="lsim-panel' + (' debrief' if is_debrief else '') + '">', unsafe_allow_html=True)
    render_agent_header(st, primary["id"], primary["name"], primary["role"], debrief=is_debrief)
    render_thread(st, beat.actor.transcript(), debrief=is_debrief)
    st.markdown('</div>', unsafe_allow_html=True)

user_input = st.chat_input(f"Message {primary['name']}…")
if user_input:
    typing_placeholder = st.empty()
    with typing_placeholder.container():
        render_typing_indicator(st, primary["id"], primary["name"])
    try:
        orch.send(user_input)
        typing_placeholder.empty()
        st.rerun()
    except AgentResponseError:
        typing_placeholder.empty()
        render_error_notice(
            st, f"Couldn't reach {primary['name']} just now — send that again in a moment."
        )

if orch.can_close_current_beat():
    if st.button("Wrap up this conversation"):
        has_more = orch.advance()
        next_scenario = orch.current_scenario if not orch.finished else None
        st.session_state.phase = (
            "transition" if (next_scenario and next_scenario.transition_text) else "chat"
        )
        st.rerun()
