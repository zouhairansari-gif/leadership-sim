"""Reviewer dossier — separate audience, separate design language from the
candidate app. Scores, evidence quotes, and the asymmetry/narrative-
integrity sections are all fine to show here; none of it should ever
reach the candidate-facing pages.
"""
import os

import streamlit as st
from dotenv import load_dotenv

from src.auth import require_password
from src.evaluator import build_dossier, find_recurring_concerns
from src.scenario import get_scenario
from src.storage import list_sessions_with_meta, load_session
from src.ui_style import escape_html, flatten_html

load_dotenv()

st.set_page_config(page_title="Reviewer Dossier", layout="centered")
require_password(st)

BADGE_STYLE = {
    "strong": ("#DCEEDB", "#2C6E3F", "Strong"),
    "mixed": ("#F7E8CE", "#8A6014", "Mixed"),
    "concerning": ("#F7DAD0", "#A8412A", "Concerning"),
    "inconclusive": ("#EDE6DA", "#7A6F5E", "Inconclusive"),
    "n/a": ("#EDE6DA", "#7A6F5E", "N/A"),
}

# Kept as a bare rule block (no <style> tag) so the exact same string can be
# reused both injected into the live Streamlit page and wrapped into a
# standalone downloadable HTML file — one definition, two destinations.
# Warm Editorial palette — kept in sync with src/ui_style.py's BASE_CSS;
# see that file's module docstring.
CSS_RULES = """
.stApp {
    background: linear-gradient(160deg, #FFF8F0 0%, #FCEEDC 100%);
}
.dossier-header {
    background: linear-gradient(120deg, #C9622E 0%, #A8442A 100%);
    color: #fff; border-radius: 12px;
    padding: 18px 22px; margin-bottom: 24px;
}
.dossier-header .session { font-size: 13px; color: #F5D9C4; margin-bottom: 4px; }
.dossier-header .title { font-size: 18px; font-weight: 600; }
.dossier-header .pilot-badge {
    display: inline-block; margin-top: 6px; font-size: 11px; font-weight: 600;
    background: rgba(255,255,255,0.2); color: #fff; padding: 2px 8px; border-radius: 20px;
}
.dossier-card {
    background: #FFFDFA; border: 1px solid #F0DCC4; border-radius: 12px;
    padding: 16px 18px; margin-bottom: 12px;
}
.dossier-card-top { display: flex; justify-content: space-between; align-items: center; }
.dossier-dim { font-size: 14px; font-weight: 600; color: #5C3A22; }
.dossier-agreement { font-size: 11px; color: #8A6A4E; margin-top: 2px; }
.dossier-badge { font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: 20px; }
.dossier-evidence {
    font-size: 13.5px; line-height: 1.6; color: #4A3320; background: #FBEAD6;
    border-left: 3px solid #D9622E; padding: 8px 12px; margin-top: 8px;
    border-radius: 0 6px 6px 0;
}
.dossier-evidence .tag { font-size: 11px; color: #A0805E; display: block; margin-bottom: 3px; }
.dossier-asym-grid { display: flex; gap: 12px; }
.dossier-asym-col {
    flex: 1; background: #FFFDFA; border: 1px solid #F0DCC4; border-radius: 12px; padding: 14px 16px;
}
.dossier-asym-col .who { font-size: 12px; font-weight: 600; color: #8A6A4E; margin-bottom: 6px; }
.dossier-delta {
    margin-top: 10px; font-size: 13px; background: #F7DAD0; color: #A8412A;
    border-radius: 8px; padding: 10px 14px;
}
.dossier-fact-row { display: flex; gap: 12px; margin-bottom: 10px; }
.dossier-fact-col { flex: 1; font-size: 13px; line-height: 1.5; padding: 10px 12px; border-radius: 8px; }
.dossier-fact-claim { background: #F8F0E4; color: #4A3320; }
.dossier-fact-actual { background: #FDF3E3; color: #6B4A0E; }
.dossier-fact-label { font-size: 11px; color: #A0805E; display: block; margin-bottom: 3px; }
.dossier-footer { margin-top: 28px; font-size: 12px; color: #A0805E; text-align: center; padding: 14px 0; border-top: 1px solid #F0DCC4; }
.dossier-recurring {
    background: #F7E8CE; color: #6B4A0E; border-radius: 8px; padding: 12px 16px;
    font-size: 13px; margin-bottom: 20px;
}

/* Printable: browser print (Ctrl/Cmd+P) on this page hides Streamlit chrome
   and the controls, leaving just the dossier itself. The standalone HTML
   download below is the more reliable path — this is a courtesy for anyone
   who'd rather print straight from the browser. */
@media print {
    header, [data-testid="stSidebar"], [data-testid="stToolbar"],
    .no-print { display: none !important; }
}
"""

st.markdown(flatten_html(f"<style>{CSS_RULES}</style>"), unsafe_allow_html=True)

if not os.environ.get("ANTHROPIC_API_KEY"):
    st.error("Set ANTHROPIC_API_KEY in your .env file (see .env.example).")
    st.stop()

st.title("Reviewer dossier")


def render_dossier_body_html(dossier: dict, candidate_id: str, is_pilot: bool) -> str:
    """Builds the dossier's inner HTML as one string, reused for both the
    live Streamlit view and the standalone download — see CSS_RULES above
    for why that matters."""
    pilot_badge = '<div class="pilot-badge">Practice / calibration run</div>' if is_pilot else ""
    html = f"""
    <div class="dossier-header">
        <div class="session">{escape_html(dossier['session_title'])}</div>
        <div class="title">{escape_html(candidate_id)} — evaluation summary</div>
        {pilot_badge}
    </div>
    """

    for beat_id, results in dossier["beat_results"].items():
        try:
            header_text = get_scenario(beat_id).title
        except KeyError:
            header_text = beat_id.replace('_', ' ').title()  # fallback if the scenario file is missing
        html += f"<h5>{escape_html(header_text)}</h5>"
        for r in results:
            bg, fg, label = BADGE_STYLE.get(r["band"], BADGE_STYLE["inconclusive"])
            evidence_html = (
                f'<div class="dossier-evidence"><span class="tag">{escape_html(r.get("evidence_turn",""))}</span>{escape_html(r["evidence_quote"])}</div>'
                if r.get("evidence_quote") else ""
            )
            html += f"""
            <div class="dossier-card">
                <div class="dossier-card-top">
                    <div>
                        <div class="dossier-dim">{escape_html(r['dimension'].replace('_', ' ').capitalize())}</div>
                        <div class="dossier-agreement">{escape_html(r['agreement'])}</div>
                    </div>
                    <span class="dossier-badge" style="background:{bg};color:{fg};">{escape_html(label)}</span>
                </div>
                {evidence_html}
            </div>
            """

    if dossier["asymmetry_results"]:
        html += "<h5>Asymmetry — same substance, different power distance</h5>"
        for a in dossier["asymmetry_results"]:
            html += f"""
            <div class="dossier-asym-grid">
                <div class="dossier-asym-col"><div class="who">{escape_html(a['beat_a'])}</div><div>{escape_html(a['excerpt_a'])}</div></div>
                <div class="dossier-asym-col"><div class="who">{escape_html(a['beat_b'])}</div><div>{escape_html(a['excerpt_b'])}</div></div>
            </div>
            <div class="dossier-delta">{escape_html(a['delta_note'])}</div>
            """

    if dossier["narrative_claims"]:
        html += "<h5>Narrative integrity — debrief vs. transcript</h5>"
        for c in dossier["narrative_claims"]:
            html += f"""
            <div class="dossier-fact-row">
                <div class="dossier-fact-col dossier-fact-claim"><span class="dossier-fact-label">Candidate said</span>{escape_html(c.get('claim',''))}</div>
                <div class="dossier-fact-col dossier-fact-actual"><span class="dossier-fact-label">Transcript shows ({escape_html(c.get('status',''))})</span>{escape_html(c.get('actual',''))}</div>
            </div>
            """

    html += '<div class="dossier-footer">Evidence dossier for human review — not an automated hiring decision.</div>'
    return html


def dossier_to_standalone_html(dossier: dict, candidate_id: str, is_pilot: bool) -> str:
    body = render_dossier_body_html(dossier, candidate_id, is_pilot)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<title>{candidate_id} — {dossier['session_title']}</title>
<style>
body {{ margin:0; padding:40px 24px; background:#FCEEDC; color:#4A3320;
        font-family:-apple-system,BlinkMacSystemFont,"Segoe UI",Helvetica,Arial,sans-serif; }}
.wrap {{ max-width:760px; margin:0 auto; }}
{CSS_RULES}
</style>
</head>
<body><div class="wrap">{body}</div></body>
</html>"""


# ---------------------------------------------------------------- candidate picker
all_sessions = list_sessions_with_meta()
if not all_sessions:
    st.info("No completed sessions yet. Run one from the main app first.")
    st.stop()

include_pilots = st.checkbox("Include practice / calibration runs", value=False)
visible_sessions = [s for s in all_sessions if include_pilots or not s["is_pilot"]]
if not visible_sessions:
    st.info("No real candidate sessions yet — only practice/calibration runs exist so far.")
    st.stop()

candidate_ids = sorted({s["candidate_id"] for s in visible_sessions})
chosen_candidate = st.selectbox("Candidate", candidate_ids)
candidate_sessions = [s for s in visible_sessions if s["candidate_id"] == chosen_candidate]

st.caption(
    f"{len(candidate_sessions)} session(s) on record for this candidate."
    + (" Scoring multiple sessions lets recurring patterns surface — a single "
       "session can't distinguish a real pattern from a one-off exercise effect."
       if len(candidate_sessions) < 2 else "")
)

if st.button("Run evaluation", key="run_eval_all"):
    for s in candidate_sessions:
        sid = s["session_id"]
        if f"dossier_{sid}" not in st.session_state:
            with st.spinner(f"Scoring {sid}…"):
                st.session_state[f"dossier_{sid}"] = build_dossier(load_session(sid))

dossiers = [
    st.session_state[f"dossier_{s['session_id']}"]
    for s in candidate_sessions
    if f"dossier_{s['session_id']}" in st.session_state
]

if dossiers:
    recurring = find_recurring_concerns(dossiers)
    if recurring:
        lines = escape_html("; ".join(
            f"{r['dimension'].replace('_', ' ')} (in {len(r['sessions'])} sessions)" for r in recurring
        ))
        st.markdown(
            f'<div class="dossier-recurring">Recurring across sessions: {lines}. '
            f"A repeated concern across independent sessions is a stronger signal "
            f"than any single result.</div>",
            unsafe_allow_html=True,
        )

    for s, dossier in zip(candidate_sessions, dossiers):
        body_html = render_dossier_body_html(dossier, chosen_candidate, s["is_pilot"])
        st.markdown(flatten_html(body_html), unsafe_allow_html=True)
        st.download_button(
            "Download this dossier as HTML",
            data=dossier_to_standalone_html(dossier, chosen_candidate, s["is_pilot"]),
            file_name=f"{chosen_candidate}_{s['session_id']}_dossier.html",
            mime="text/html",
            key=f"dl_{s['session_id']}",
        )
        st.divider()
