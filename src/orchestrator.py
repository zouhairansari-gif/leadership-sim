"""Orchestrator: runs one candidate through one canonical session.

Owns the things a single Actor can't: which beat we're on, session-level
flags that let a later beat's hidden_info branch on an earlier beat's
outcome (see beat2_farhans_dip.yaml), and the treatment-log updates that
make agent memory feel earned rather than decorative.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from anthropic import Anthropic

from src.agents import Actor
from src.scenario import Scenario, get_scenario
from src.session_config import get_session_config

_client = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


CLASSIFIER_MODEL = os.environ.get("EVALUATOR_MODEL", "claude-sonnet-5")


@dataclass
class BeatRecord:
    scenario_id: str
    actor: Actor
    candidate_turns: int = 0


@dataclass
class Session:
    session_id: str
    config: dict
    beat_order: list = field(default_factory=list)   # scenario ids, in order
    current_index: int = 0
    flags: dict = field(default_factory=dict)         # session-level branching flags
    beats: dict = field(default_factory=dict)          # scenario_id -> BeatRecord
    finished: bool = False

    @classmethod
    def start(cls, session_id: str) -> "Session":
        config = get_session_config(session_id)
        return cls(session_id=session_id, config=config, beat_order=list(config["beats"]))

    @property
    def current_scenario_id(self) -> str:
        return self.beat_order[self.current_index]

    @property
    def current_scenario(self) -> Scenario:
        return get_scenario(self.current_scenario_id)

    @property
    def current_beat(self) -> BeatRecord:
        sid = self.current_scenario_id
        if sid not in self.beats:
            scenario = get_scenario(sid)
            primary = scenario.primary_agent
            actor = Actor.from_scenario_agent(primary, session_flags=self.flags)
            self.beats[sid] = BeatRecord(scenario_id=sid, actor=actor)
        return self.beats[sid]

    def can_close_current_beat(self) -> bool:
        scenario = self.current_scenario
        return self.current_beat.candidate_turns >= scenario.min_turns

    def send(self, message: str) -> str:
        """Send the candidate's message to the current beat's agent."""
        scenario = self.current_scenario
        beat = self.current_beat
        inject = self._maybe_timeline_event(scenario, beat)
        reply = beat.actor.respond(message, inject_event=inject)
        beat.candidate_turns += 1
        self._note_treatment(beat)
        return reply

    def _maybe_timeline_event(self, scenario: Scenario, beat: BeatRecord) -> str | None:
        for event in scenario.timeline_events:
            trigger = event.get("trigger", "")
            # Minimal trigger language: "turn_count >= N"
            if trigger.startswith("turn_count >="):
                threshold = int(trigger.split(">=")[1].strip())
                if beat.candidate_turns + 1 == threshold:
                    return event.get("content")
        return None

    def _note_treatment(self, beat: BeatRecord) -> None:
        """Cheap heuristic note, not a model call — keeps the treatment log
        populated without a classifier round-trip on every single turn.
        Good enough for a skeleton; swap for a real classifier if the
        heuristic proves too coarse."""
        last_candidate_msg = beat.actor.history[-2]["content"] if len(beat.actor.history) >= 2 else ""
        note = f"Candidate said: \"{last_candidate_msg[:120]}\""
        beat.actor.note_treatment(note)

    def advance(self) -> bool:
        """Close the current beat, run its classifier if it has one, and
        move to the next. Returns False if the session is already finished."""
        scenario = self.current_scenario
        beat = self.current_beat

        if scenario.classifier:
            flag_value = self._run_classifier(scenario, beat)
            self.flags[scenario.classifier["flag"]] = flag_value

        if self.current_index + 1 >= len(self.beat_order):
            self.finished = True
            return False

        self.current_index += 1
        return True

    def _run_classifier(self, scenario: Scenario, beat: BeatRecord) -> str:
        cfg = scenario.classifier
        transcript_text = "\n".join(
            f"{t['speaker']}: {t['text']}" for t in beat.actor.transcript()
        )
        try:
            response = _get_client().messages.create(
                model=CLASSIFIER_MODEL,
                max_tokens=10,
                system=cfg["prompt"],
                messages=[{"role": "user", "content": transcript_text}],
            )
        except Exception:
            # Degrade to the safe default rather than blocking the candidate's
            # session — but record that this happened, so a reviewer reading
            # the dossier later knows this branch was a fallback, not a real
            # read of what happened in the beat.
            self.flags[f"{cfg['flag']}_classifier_error"] = True
            return cfg["options"][0]

        text = "".join(b.text for b in response.content if b.type == "text").strip().lower()
        for option in cfg["options"]:
            if option in text:
                return option
        return cfg["options"][0]  # safe fallback

    def all_transcripts(self) -> dict:
        """scenario_id -> transcript, for every beat run so far."""
        return {sid: rec.actor.transcript() for sid, rec in self.beats.items()}

    def to_dict(self) -> dict:
        """Serialize for storage (src/storage.py)."""
        return {
            "session_id": self.session_id,
            "config_id": self.config["id"],
            "flags": self.flags,
            "finished": self.finished,
            "beats": {
                sid: {
                    "candidate_turns": rec.candidate_turns,
                    "transcript": rec.actor.transcript(),
                }
                for sid, rec in self.beats.items()
            },
        }
