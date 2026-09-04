"""Evaluator: turns transcripts into the reviewer dossier.

Three separate scoring mechanisms, matching the reviewer-dossier design:
  1. evaluate_beat        - per-dimension bands with evidence quotes,
                             run as multiple independent passes so
                             disagreement surfaces as "inconclusive"
                             rather than a falsely confident average.
  2. evaluate_asymmetry    - diffs two beats covering the same substance
                             at different power distances.
  3. evaluate_narrative_integrity - fact-checks the debrief beat against
                             the transcripts of the beats before it.

No score without a quote. If the model can't cite a specific line, that's
a signal the dimension wasn't observable in this session, not something to
paper over with a plausible-sounding rating.
"""
from __future__ import annotations

import json
import os
from collections import Counter

from anthropic import Anthropic

from src.scenario import get_scenario
from src.session_config import get_session_config

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


EVALUATOR_MODEL = os.environ.get("EVALUATOR_MODEL", "claude-sonnet-5")
PASSES_PER_DIMENSION = int(os.environ.get("EVALUATOR_PASSES", "3"))

VALID_BANDS = {"strong", "mixed", "concerning", "n/a"}


def _transcript_text(transcript: list[dict]) -> str:
    return "\n".join(f"{t['speaker']}: {t['text']}" for t in transcript)


def _call_json(system: str, user: str) -> dict:
    """One model call, expecting a bare JSON object back. Best-effort parse
    — a malformed response degrades to an 'inconclusive' result rather than
    crashing the whole dossier build."""
    response = _get_client().messages.create(
        model=EVALUATOR_MODEL,
        max_tokens=500,
        system=system + "\n\nRespond with ONLY a JSON object, no other text, no markdown fences.",
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(b.text for b in response.content if b.type == "text").strip()
    text = text.strip("`")
    if text.startswith("json"):
        text = text[4:].strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def evaluate_beat(scenario_id: str, transcript: list[dict]) -> list[dict]:
    """Runs the beat's rubric dimensions, each as PASSES_PER_DIMENSION
    independent calls, and aggregates into a band + agreement note."""
    scenario = get_scenario(scenario_id)

    if not transcript:
        # A beat can end up recorded with zero turns — an interrupted
        # session, a stale record from an earlier run, etc. Sending an
        # empty message to the API is a guaranteed 400, and a reviewer
        # should see "no data" rather than a crashed page.
        return [
            {
                "dimension": dim["dimension"], "band": "inconclusive",
                "agreement": "no transcript recorded for this beat",
                "evidence_quote": "", "evidence_turn": "",
            }
            for dim in scenario.evaluation_rubric
        ]

    transcript_text = _transcript_text(transcript)
    results = []

    for dim in scenario.evaluation_rubric:
        passes = []
        for _ in range(PASSES_PER_DIMENSION):
            system = (
                f"You are scoring a leadership-simulation transcript on one dimension: "
                f"{dim['dimension']}.\n{dim['prompt_for_evaluator']}\n\n"
                'Return JSON: {"band": "strong" | "mixed" | "concerning" | "n/a", '
                '"evidence_quote": "<short exact quote from the transcript, or empty if n/a>", '
                '"evidence_turn": "<e.g. turn 5, or empty>"}. '
                "Use n/a only if the rubric prompt explicitly says this dimension may not apply. "
                "Never invent a quote — if you can't find one, the band should not be 'strong' or 'concerning'."
            )
            result = _call_json(system, transcript_text)
            band = result.get("band", "").lower()
            if band in VALID_BANDS:
                passes.append(result)

        if not passes:
            results.append({
                "dimension": dim["dimension"], "band": "inconclusive",
                "agreement": "0 valid passes", "evidence_quote": "", "evidence_turn": "",
            })
            continue

        bands = [p["band"] for p in passes]
        band_counts = Counter(bands)
        top_band, top_count = band_counts.most_common(1)[0]

        if top_count >= (len(passes) // 2 + 1):
            best = next(p for p in passes if p["band"] == top_band)
            results.append({
                "dimension": dim["dimension"],
                "band": top_band,
                "agreement": f"{top_count} of {len(passes)} passes agreed",
                "evidence_quote": best.get("evidence_quote", ""),
                "evidence_turn": best.get("evidence_turn", ""),
            })
        else:
            results.append({
                "dimension": dim["dimension"],
                "band": "inconclusive",
                "agreement": f"{top_count} of {len(passes)} passes agreed — reviewed as low-confidence",
                "evidence_quote": passes[0].get("evidence_quote", ""),
                "evidence_turn": passes[0].get("evidence_turn", ""),
            })

    return results


def evaluate_asymmetry(scenario_a_id: str, transcript_a: list, scenario_b_id: str, transcript_b: list) -> dict:
    if not transcript_a or not transcript_b:
        return {
            "excerpt_a": "", "excerpt_b": "",
            "delta_note": "One or both beats have no recorded transcript — nothing to compare.",
        }
    scenario_b = get_scenario(scenario_b_id)
    rubric = scenario_b.evaluation_rubric[0]  # asymmetry beats have exactly one rubric entry
    system = (
        f"{rubric['prompt_for_evaluator']}\n\n"
        'Return JSON: {"excerpt_a": "<matched quote from transcript A>", '
        '"excerpt_b": "<matched quote from transcript B>", '
        '"delta_note": "<one or two sentences on the behavioral difference, or empty if none found>"}'
    )
    user = f"TRANSCRIPT A ({scenario_a_id}):\n{_transcript_text(transcript_a)}\n\nTRANSCRIPT B ({scenario_b_id}):\n{_transcript_text(transcript_b)}"
    result = _call_json(system, user)
    return {
        "excerpt_a": result.get("excerpt_a", ""),
        "excerpt_b": result.get("excerpt_b", ""),
        "delta_note": result.get("delta_note", ""),
    }


def evaluate_narrative_integrity(debrief_scenario_id: str, debrief_transcript: list, prior_transcripts: dict, session_flags: dict | None = None) -> list[dict]:
    if not debrief_transcript:
        return []
    scenario = get_scenario(debrief_scenario_id)
    rubric = scenario.evaluation_rubric[0]
    prior_text = "\n\n".join(
        f"--- {sid} ---\n{_transcript_text(t)}" for sid, t in prior_transcripts.items()
    )
    flags_text = ", ".join(f"{k}={v}" for k, v in (session_flags or {}).items()) or "(none set)"
    system = (
        f"{rubric['prompt_for_evaluator']}\n\n"
        'Return JSON: {"claims": [{"claim": "<what the candidate said in the debrief>", '
        '"actual": "<what the transcripts actually show>", '
        '"status": "accurate" | "omitted" | "inconsistent"}]}. '
        "List at most 3 claims, the most significant ones."
    )
    user = (
        f"SESSION FLAGS: {flags_text}\n\n"
        f"DEBRIEF TRANSCRIPT:\n{_transcript_text(debrief_transcript)}\n\n"
        f"PRIOR TRANSCRIPTS:\n{prior_text}"
    )
    result = _call_json(system, user)
    return result.get("claims", [])


def build_dossier(session_data: dict) -> dict:
    """Full dossier for a completed (or in-progress) session, matching the
    reviewer-dossier layout: per-beat dimension cards, asymmetry section,
    narrative-integrity section."""
    config = get_session_config(session_data["config_id"])
    transcripts = {sid: b["transcript"] for sid, b in session_data["beats"].items()}

    beat_results = {}
    for sid in transcripts:
        scenario = get_scenario(sid)
        if not scenario.scored:
            continue  # warm-up and other unscored beats never reach the evaluator
        if sid == config.get("debrief_beat"):
            continue  # scored separately, not on its own rubric
        is_asymmetry_beat = any(sid in pair for pair in config.get("asymmetry_pairs", []))
        if is_asymmetry_beat and sid != config["asymmetry_pairs"][0][0]:
            continue  # the second half of a pair has no standalone rubric
        beat_results[sid] = evaluate_beat(sid, transcripts[sid])

    asymmetry_results = []
    for beat_a, beat_b in config.get("asymmetry_pairs", []):
        if beat_a in transcripts and beat_b in transcripts:
            asymmetry_results.append({
                "beat_a": beat_a, "beat_b": beat_b,
                **evaluate_asymmetry(beat_a, transcripts[beat_a], beat_b, transcripts[beat_b]),
            })

    narrative_claims = []
    debrief_id = config.get("debrief_beat")
    if debrief_id and debrief_id in transcripts:
        prior = {sid: t for sid, t in transcripts.items() if sid != debrief_id}
        narrative_claims = evaluate_narrative_integrity(
            debrief_id, transcripts[debrief_id], prior, session_flags=session_data.get("flags", {})
        )

    return {
        "session_id": session_data["session_id"],
        "session_title": config["title"],
        "flags": session_data.get("flags", {}),
        "beat_results": beat_results,
        "asymmetry_results": asymmetry_results,
        "narrative_claims": narrative_claims,
    }


def find_recurring_concerns(dossiers: list[dict]) -> list[dict]:
    """Given multiple sessions' dossiers for the same candidate, find
    dimensions that came back "concerning" in more than one independent
    session. A single session can't distinguish a real pattern from a
    one-off bad exercise — assessment-center research is clear that scores
    cluster by exercise more than by any stable trait. This is the actual
    mitigation: it only means something once 2+ sessions exist."""
    if len(dossiers) < 2:
        return []

    occurrences: dict[str, list[str]] = {}
    for dossier in dossiers:
        seen_this_session = set()
        for beat_id, results in dossier["beat_results"].items():
            for r in results:
                if r["band"] == "concerning" and r["dimension"] not in seen_this_session:
                    occurrences.setdefault(r["dimension"], []).append(dossier["session_id"])
                    seen_this_session.add(r["dimension"])

    return [
        {"dimension": dim, "sessions": sessions}
        for dim, sessions in occurrences.items()
        if len(sessions) >= 2
    ]
