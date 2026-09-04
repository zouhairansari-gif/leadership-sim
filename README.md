# Leadership Simulation Assessment

Agent-based scenario simulation for evaluating *how* a candidate thinks and
acts under pressure, rather than the quality of a task output. Candidates
run a chained "session" of workplace conversations with AI-played
colleagues; a separate reviewer dossier scores the transcripts against an
evidence-cited rubric.

## What's built: two canonical sessions, selectable at the start screen

Both share the same unscored warm-up beat (`beat0_warmup`) before anything
that counts starts.

### Session A — "The Week With Amara"

1. **The Friday Deadline** — a moved-up deadline conversation with Amara
   (senior analyst). Sets a session flag (`beat1_outcome`) based on whether
   the candidate protected the team or transmitted the pressure downward.
2. **Farhan's Dip** — a performance conversation with Farhan. His hidden
   cause *branches on Beat 1's outcome*: if you transmitted the pressure,
   his dip is fallout from that decision; if you protected the team, it's
   an unrelated personal matter. Same question, different honest answer,
   depending on what you actually did earlier.
3. **The Stakeholder Question** — a senior stakeholder challenges the same
   Farhan situation. Scored as a diff against Beat 2, not standalone —
   this is the asymmetry mechanic: does ownership present downward
   disappear when the same story is told upward.
4. **End-of-Week Check-In** — closing debrief with your manager. Scored for
   narrative integrity against the actual transcripts of Beats 1–3.

### Session B — "The Quarter-End Number"

No asymmetry pair this time — its mechanic is **propagation**: does a
compromise made privately survive being restated to someone senior.

1. **The Methodology Call** — Meera, senior analyst, pushes back on the
   candidate's proposed approach and turns out to be right. Tests live
   disagreement handling and whether being wrong later gets acknowledged.
2. **Malik Needs Meera Too** — a peer manager needs the same analyst for
   his own deadline, no hierarchy either way. Tests influence without
   authority, plus a continuity check on whether Meera's Beat 1
   contribution gets credited.
3. **The Number** — Zeina brings a technically defensible but knowingly
   optimistic figure right before the deadline. Sets a session flag
   (`number_corrected`) based on whether the candidate pushed back on it.
4. **Presenting the Number** — debrief with your manager. Scored for
   narrative integrity *and* for propagation: if the number was never
   corrected, does it get presented upward as settled fact.

### Session C — "The Long Game"

Center of gravity is different again — this one's about investing in and
crediting people, not crisis response or integrity under pressure. Built
to directly answer two structured-interview questions from the HBR
article this whole project started from ("who helped you succeed," "how
did you develop an associate") as live mechanics instead of self-report.

1. **The Stretch Ask** — Aisha, a junior analyst, asks for real
   development. Tests genuine investment versus a generic brush-off.
2. **The Two Updates** — reporting Aisha's win and a separate team miss to
   your manager in the same conversation. Tests credit attribution and
   how the miss gets framed.
3. **What Sana Said** — a colleague blames Rohan (not present) for
   something, only partly fairly. Sets a session flag (`rohan_judgment`)
   based on whether the candidate investigates or accepts it at face
   value.
4. **One More Thing** — debrief with your manager. Scored for narrative
   integrity, and — if Beat 3's framing was accepted uncritically — for
   whether new information about Rohan gets acknowledged and corrected.

### Cross-session dimension tracking

Sessions A, B, and C deliberately share dimension names where they're
testing the same underlying construct, so the reviewer dossier's
recurring-concerns note (`find_recurring_concerns` in `src/evaluator.py`)
has something real to triangulate rather than three isolated readings:

- `accountability_under_error` — owning being wrong — appears in **all
  three** sessions (A's Beat 2, B's Beat 1, C's Beat 4).
- `narrative_integrity` — every debrief, all three sessions.
- `credit_attribution` — B's Beat 2, C's Beat 2.
- `diagnosis_before_judgment` — A's Beat 2, C's Beat 3 (same construct:
  investigate before accepting a convenient framing about someone who
  isn't there to respond).
- `psychological_safety_signal` — A's Beat 1, C's Beat 1.

Known gap, not yet fixed: `find_recurring_concerns` only scans
`beat_results`, never `asymmetry_results` or `narrative_claims` — so A's
`asymmetry_delta` and B's `propagation`, which are conceptually close
(both are "does the truth survive being said to someone senior"), can't
cross-track yet even though they're related. That needs the aggregation
function itself widened, not just a naming fix.

## Process features

- **Consent/disclosure screen.** Before a candidate can begin, they see a
  plain-language statement that the conversation will be used to evaluate
  leadership behavior, and must check an explicit consent box. No
  mechanics are revealed — see the module docstring in `app.py`.
- **Calibration/pilot mode.** A checkbox on the start screen marks a run as
  practice rather than a real candidate. The reviewer dossier excludes
  pilot runs by default and badges them clearly when included.
- **Multi-session view.** The reviewer page groups all sessions by
  candidate and, once 2+ sessions exist for the same person, surfaces
  dimensions that came back "concerning" in more than one independent
  session (`src/evaluator.py::find_recurring_concerns`). This is the actual
  mitigation for the exercise-effect problem — assessment-center research
  is clear that scores cluster by exercise more than by any stable
  pattern, so a single session's "concerning" rating shouldn't be read as
  a trait on its own.

## Design features

- **A designed failure state.** If a model call fails mid-conversation, the
  candidate sees a calm, plain notice ("Couldn't reach Amara just now —
  send that again") instead of a raw Python traceback. The failed turn is
  rolled back cleanly (`AgentResponseError` in `src/agents.py`) rather than
  leaving an orphaned message in the transcript. The Beat-1→Beat-2
  classifier degrades the same way — falls back to a safe default and
  leaves an honest flag (`{flag}_classifier_error`) for the reviewer,
  rather than silently guessing or crashing the session.
- **`prefers-reduced-motion` respected.** The beat-opening fade-in turns
  off entirely for anyone with that OS setting.
- **Mobile reflow.** Tighter padding, wider bubble proportions, and
  smaller type below a ~480px viewport.
- **Exportable dossier.** Each dossier has a "Download as HTML" button
  producing a fully standalone file — shareable, printable, and openable
  without Streamlit running. The live page also has print-friendly CSS as
  a lighter-weight fallback.
- **Illustrated avatars, not letter circles.** Head-and-shoulders silhouette
  (identical shape across every agent, by design — see `ui_style.py`'s
  avatar docstring for why), with role color as "clothing," and skin tone
  + hairstyle derived deterministically from `agent_id` so the same agent
  always looks the same but new agents get automatic variety without
  hand-curating each one. A real typing indicator (sound-wave bars + "X is
  typing…") replaces the blank spinner while waiting on a reply.
- **A smooth transition between sessions.** Finishing a session doesn't
  dead-end at a completion screen — if there's a next session in
  `SESSION_SEQUENCE` (`src/session_config.py`, currently A → B → C), the
  candidate sees the same visual transition used between beats, with a
  Continue button carrying the same candidate_id and pilot flag straight
  into the next session without re-entering consent. There's still an
  explicit "I'm finished for now" way out — nobody's funneled through all
  three against their will.

- **Password gate.** One shared password, not per-user accounts — set via
  `APP_PASSWORD`, checked on every page independently (a direct link to the
  Reviewer Dossier page would otherwise skip it entirely). If `APP_PASSWORD`
  isn't set, the gate is a no-op — fine for local development, but it means
  deployment *always* needs this secret set or the app runs fully open.

## Deploying to Streamlit Community Cloud

The app only needs to be reachable by other people for "password-protect
it" to matter at all — right now `streamlit run app.py` only serves to
your own machine. These steps make it actually reachable:

1. **Push the code to a GitHub repo.** Community Cloud deploys from GitHub,
   public or private. Create a repo, push this folder to it. `.gitignore`
   already excludes `venv/`, `.env`, and `data/sessions/*.json` — don't
   commit your real API key.
2. **Go to [share.streamlit.io](https://share.streamlit.io)** and sign in
   with the GitHub account that owns the repo.
3. **Create a new app**, pointing it at that repo, branch `main`, entry
   point `app.py`.
4. **Set secrets before the first real run** — in the app's Settings →
   Secrets panel, paste (as TOML, one `KEY = "value"` per line):
   ```
   ANTHROPIC_API_KEY = "sk-ant-..."
   ACTOR_MODEL = "claude-sonnet-5"
   EVALUATOR_MODEL = "claude-sonnet-5"
   EVALUATOR_PASSES = "3"
   APP_PASSWORD = "choose-something-here"
   ```
   `APP_PASSWORD` is the one that actually matters here — without it, the
   app deploys fully open regardless of anything else.
5. **Deploy.** Community Cloud installs `requirements.txt` and starts the
   app automatically; it redeploys on every push to the branch.

**Known limitation, worth treating as a blocker rather than an eventual
fix:** session data is stored as local JSON files
(`data/sessions/*.json`), and Community Cloud's filesystem is ephemeral —
it can be wiped on a restart or redeploy. Anyone who actually runs a
session on the deployed app risks losing that record. Don't rely on this
for real candidate or pilot data until storage is moved to something
persistent (a real database) — `src/storage.py`'s own docstring already
says as much.

## Setup

```bash
cd leadership-sim
python -m venv venv
source venv/bin/activate      # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env          # then add your ANTHROPIC_API_KEY
streamlit run app.py
```

Open the app, run through the four beats as the candidate would. When a
session finishes it's written to `data/sessions/<run_id>.json`. Then look
at the sidebar page picker (or visit the "Reviewer Dossier" page) to score
it — that page reads any completed session from disk and runs the
evaluator on demand, so it can be opened in a separate browser session
entirely, the way a real reviewer would.

## Structure

```
leadership-sim/
  app.py                       Candidate-facing app (Session A runner)
  pages/
    1_Reviewer_Dossier.py       Reviewer view — separate design language, on purpose
  src/
    scenario.py                 YAML loader/schema (transitions, branching, classifiers)
    agents.py                   Actor persona class + hidden_info_variants resolution
    orchestrator.py              Session class — beat sequencing, classifier passes, treatment log
    evaluator.py                 Rubric scoring (multi-pass agreement), asymmetry diff, narrative integrity
    session_config.py            Canonical session definitions (SESSION_A)
    storage.py                   JSON-file session persistence (swap for a real DB before real candidates)
    ui_style.py                  Candidate-view CSS + bubble rendering — matches the approved mockup
  scenarios/
    beat0_warmup.yaml
    beat1_deadline.yaml
    beat2_farhans_dip.yaml
    beat3_senior_stakeholder.yaml
    beat4_debrief.yaml
    sessionb_beat1_dissent.yaml
    sessionb_beat2_resource_conflict.yaml
    sessionb_beat3_misreport.yaml
    sessionb_beat4_debrief.yaml
    sessionc_beat1_development.yaml
    sessionc_beat2_credit.yaml
    sessionc_beat3_absent_colleague.yaml
    sessionc_beat4_debrief.yaml
  data/sessions/                Completed session JSON lands here (gitignored — see below)
```

## Design principles, still binding as you extend this

1. **Scenarios are data, not code.** New beat = new YAML file. Never
   hardcode scenario content in Python.
2. **Actors are separate model calls.** One persona, one system prompt, one
   private state. Never merge personas into a shared prompt.
3. **The evaluator never sees itself as an actor.** Scoring is a distinct
   pass, run after the transcript closes, on a separate model call from
   any actor.
4. **No score without a quote.** Every dimension rating cites a transcript
   span. If the evaluator can't quote one, it shouldn't rate strong or
   concerning.
5. **No affect/emotion inference from tone or "vibes."** Score decisions,
   questions asked, and behavioral asymmetries — text and choices only.
   Keeps this clear of the EU AI Act's prohibition on emotion recognition
   in hiring contexts, and keeps the measurement honest either way.
6. **Candidate screens never show what's being measured.** No visible
   scores, rubrics, or beat-count progress indicators. The one deliberate
   register shift is the debrief beat's header — see `ui_style.py`.

## Known gaps in this skeleton, worth fixing before anyone real uses it

- `Session._note_treatment` is a cheap heuristic (logs the raw candidate
  message), not a real classifier. Good enough to prove the treatment-log
  plumbing works; swap for a proper "how was this agent treated" model
  call before the persistent-memory mechanic is trustworthy.
- `storage.py` is flat JSON files, no auth, no concurrency handling. Fine
  for local development, not for anything touching real candidate data —
  session records are exactly what the EU AI Act's logging/documentation
  obligations apply to.
- No adverse-impact testing has been done on any scenario. Do this before
  running real candidates through it, not after.
- Beat transitions use a simple `turn_count >= N` trigger language in
  YAML. Fine for the four beats here; will need a slightly richer
  condition grammar if later scenarios need anything more complex.

## Next build step

Three canonical sessions exist now, all running through the same
orchestrator and evaluator with zero code changes to add C after B — the
actual test of whether "scenarios are data" held, twice over. Dimension
names are now deliberately shared across sessions where they test the
same construct (see "Cross-session dimension tracking" above), so the
recurring-concerns note has real signal to work with instead of three
isolated readings. What's still open: the reviewer dossier's inline
legends, per-line quote attribution, per-beat summaries, the
session-level scorecard, and the post-session organogram reveal — all
speced in earlier design passes but not yet built. Also open: widening
`find_recurring_concerns` to scan `asymmetry_results` and
`narrative_claims`, not just `beat_results` — see the known-gap note
above.
