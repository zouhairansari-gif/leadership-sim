"""Loads and validates scenario YAML files.

Scenarios are data, not code. If you're editing scenario *content* in this
file, stop — go edit or add a YAML file in scenarios/ instead.

Extended (Session A build) to support:
  - transition_text: shown in the interstitial before this beat starts
  - min_turns / close_after_turns: gates the candidate's "wrap up" control
  - agents[].hidden_info_variants: branches an agent's hidden info on a
    session-level flag set by a prior beat's classifier (see orchestrator.py)
  - classifier: optional config telling the orchestrator how to derive a
    session flag from this beat's transcript once it closes
"""
from __future__ import annotations

import glob
import os
from dataclasses import dataclass, field

import yaml

SCENARIOS_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "scenarios")

REQUIRED_TOP_LEVEL = [
    "id", "title", "description", "dimensions_targeted",
    "candidate_briefing", "world_state", "agents", "evaluation_rubric",
]
REQUIRED_AGENT_KEYS = ["id", "name", "role", "status", "disposition"]


@dataclass
class Scenario:
    id: str
    title: str
    description: str
    dimensions_targeted: list
    candidate_briefing: str
    world_state: dict
    agents: list                      # list of dicts, one per persona
    timeline_events: list = field(default_factory=list)
    evaluation_rubric: list = field(default_factory=list)
    transition_text: str = ""         # shown in the interstitial leading into this beat
    min_turns: int = 3                # candidate can't "wrap up" before this many of their turns
    close_after_turns: int = 10       # auto-suggest wrap-up past this many, still candidate-initiated
    classifier: dict | None = None    # {"flag": "beat1_outcome", "options": [...], "prompt": "..."}
    register: str = "workplace"       # "workplace" | "debrief" — drives UI chrome
    scored: bool = True               # False for unscored beats (e.g. the warm-up)

    @property
    def agent_ids(self):
        return [a["id"] for a in self.agents]

    @property
    def primary_agent(self) -> dict:
        return self.agents[0]


def _validate(raw: dict, path: str) -> None:
    missing = [k for k in REQUIRED_TOP_LEVEL if k not in raw]
    if missing:
        raise ValueError(f"{path}: missing top-level keys {missing}")
    for agent in raw["agents"]:
        missing_agent_keys = [k for k in REQUIRED_AGENT_KEYS if k not in agent]
        if missing_agent_keys:
            raise ValueError(
                f"{path}: agent {agent.get('id', '?')} missing keys {missing_agent_keys}"
            )
        if "hidden_info" not in agent and "hidden_info_variants" not in agent:
            raise ValueError(
                f"{path}: agent {agent['id']} needs hidden_info or hidden_info_variants"
            )


def load_scenario(path: str) -> Scenario:
    with open(path, "r", encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    _validate(raw, path)
    return Scenario(
        id=raw["id"],
        title=raw["title"],
        description=raw["description"],
        dimensions_targeted=raw["dimensions_targeted"],
        candidate_briefing=raw["candidate_briefing"],
        world_state=raw["world_state"],
        agents=raw["agents"],
        timeline_events=raw.get("timeline_events", []),
        evaluation_rubric=raw["evaluation_rubric"],
        transition_text=raw.get("transition_text", ""),
        min_turns=raw.get("min_turns", 3),
        close_after_turns=raw.get("close_after_turns", 10),
        classifier=raw.get("classifier"),
        register=raw.get("register", "workplace"),
        scored=raw.get("scored", True),
    )


def list_scenarios() -> list[Scenario]:
    paths = sorted(glob.glob(os.path.join(SCENARIOS_DIR, "*.yaml")))
    return [load_scenario(p) for p in paths]


def get_scenario(scenario_id: str) -> Scenario:
    for s in list_scenarios():
        if s.id == scenario_id:
            return s
    raise KeyError(f"No scenario with id={scenario_id!r} found in {SCENARIOS_DIR}")
