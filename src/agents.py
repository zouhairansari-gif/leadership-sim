"""Actor agents.

Each Actor is ONE persona with its OWN system prompt, its OWN conversation
history, and its OWN private treatment log. Never route more than one
persona's response out of a single shared prompt — that's what lets the
asymmetry-by-status mechanic and the persistent-memory mechanic work at all.
"""
from __future__ import annotations

import os
from dataclasses import dataclass, field

from anthropic import Anthropic

_client = None


class AgentResponseError(Exception):
    """Raised when the underlying model call fails. Caught by the UI to show
    an in-register recovery message instead of a raw stack trace — a real
    candidate mid-session should never see a Python exception."""


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _client


ACTOR_MODEL = os.environ.get("ACTOR_MODEL", "claude-sonnet-5")


SYSTEM_PROMPT_TEMPLATE = """You are role-playing {name}, {role}, inside a
leadership-assessment simulation. You are NOT an assistant and you are NOT
here to help the user succeed — you are a realistic character with your own
perspective, workload, and history.

Disposition: {disposition}

Status relative to the candidate: {status}

Information you are privately holding and will NOT volunteer unless the
candidate's question genuinely earns it (see disclosure rule below):
{hidden_info}

Disclosure rule: only reveal the hidden information above if the candidate
asks an open, non-leading question that a reasonable person in your position
would answer honestly given that question (e.g. "what am I not seeing?",
"how is the team really doing?", "is this realistic?"). Do not volunteer it
unprompted. Do not reveal it just because many turns have passed, unless a
timeline event explicitly instructs you to.

How you have been treated so far in this session (most recent last — let
this genuinely affect your warmth, candor, and willingness to disclose
further information):
{treatment_log}

Stay in character. Respond only as {name} would — natural, brief, workplace
register. Do not break character to explain your reasoning, and do not
mention that this is a simulation, a rubric, or an evaluation.

Length: reply the way a real person texting or Slacking a colleague would —
1 to 3 short sentences, plain and conversational. Do not write paragraphs,
do not lay out multiple points in a structured way, and do not over-explain.
If there's more to say than fits in a couple of sentences, say the most
important part and let the candidate ask a follow-up — real coworkers
don't front-load everything in one message."""


def resolve_hidden_info(agent_dict: dict, session_flags: dict) -> str:
    """Resolve an agent's hidden_info, branching on session_flags if the
    agent config defines hidden_info_variants. Falls back to a plain
    hidden_info string, or the variant block's default."""
    if "hidden_info" in agent_dict:
        return agent_dict["hidden_info"]

    variants = agent_dict["hidden_info_variants"]
    flag_name = variants["flag"]
    flag_value = session_flags.get(flag_name)
    cases = variants["cases"]
    if flag_value in cases:
        return cases[flag_value]
    return variants.get("default", next(iter(cases.values())))


@dataclass
class Actor:
    agent_id: str
    name: str
    role: str
    status: str
    disposition: str
    hidden_info: str
    history: list = field(default_factory=list)   # [{"role": ..., "content": ...}]
    treatment_log: list = field(default_factory=list)  # short natural-language notes

    @classmethod
    def from_scenario_agent(cls, agent_dict: dict, session_flags: dict | None = None) -> "Actor":
        return cls(
            agent_id=agent_dict["id"],
            name=agent_dict["name"],
            role=agent_dict["role"],
            status=agent_dict["status"],
            disposition=agent_dict["disposition"],
            hidden_info=resolve_hidden_info(agent_dict, session_flags or {}),
        )

    def _system_prompt(self) -> str:
        treatment = "\n".join(f"- {note}" for note in self.treatment_log) or "- (no prior interaction)"
        return SYSTEM_PROMPT_TEMPLATE.format(
            name=self.name,
            role=self.role,
            disposition=self.disposition,
            status=self.status,
            hidden_info=self.hidden_info,
            treatment_log=treatment,
        )

    def respond(self, candidate_message: str, inject_event: str | None = None) -> str:
        """Send the candidate's message to this actor and return its reply.

        `inject_event` is optional scenario-timeline content (e.g. a new
        constraint) appended as a system-level note before the actor replies
        — used by the orchestrator, not called directly by the UI.
        """
        self.history.append({"role": "user", "content": candidate_message})

        system = self._system_prompt()
        if inject_event:
            system += f"\n\nJust happened, factor this in naturally: {inject_event}"

        response = None
        try:
            response = _get_client().messages.create(
                model=ACTOR_MODEL,
                max_tokens=150,
                system=system,
                messages=self.history,
            )
        except Exception as exc:
            self.history.pop()  # roll back the candidate message — no reply was produced
            raise AgentResponseError(str(exc)) from exc

        text = "".join(block.text for block in response.content if block.type == "text")
        self.history.append({"role": "assistant", "content": text})
        return text

    def note_treatment(self, note: str) -> None:
        """Orchestrator calls this after each turn to log how the candidate
        treated this agent, in plain language (not a score). Keep it short —
        this feeds back into the system prompt on every subsequent turn."""
        self.treatment_log.append(note)

    def transcript(self) -> list[dict]:
        """Plain [{speaker, text}] view of this actor's conversation, for
        the evaluator and the reviewer dossier."""
        out = []
        for turn in self.history:
            speaker = "Candidate" if turn["role"] == "user" else self.name
            out.append({"speaker": speaker, "text": turn["content"]})
        return out
